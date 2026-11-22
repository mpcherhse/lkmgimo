"""Электронная справка: PDF (reportlab) с QR-кодом на страницу проверки подлинности.
Проверка по коду показывает только номер, вид документа, дату и маскированные инициалы — без персональных данных.
В бою справку подписывает УКЭП уполномоченного лица; в концепте — пометка «образец, не является документом»."""
import io
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Path as PathParam, Request

from . import config, ratelimit
from .timetable import MSK, human_date
from .web import ApiError, client_ip, database

router = APIRouter()
FONTS = Path(__file__).resolve().parent / "resources" / "fonts"
_registered = False


def _fonts():
    global _registered
    if _registered:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("PTSans", str(FONTS / "PT_Sans-Web-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("PTSans-Bold", str(FONTS / "PT_Sans-Web-Bold.ttf")))
    _registered = True


def verify_url(code):
    return f"{config.PUBLIC_URL}/verify/{code}"


def _wrap(c, text, x, y, width, font, size, leading):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words, line = text.split(), ""
    for w in words:
        trial = (line + " " + w).strip()
        if stringWidth(trial, font, size) > width and line:
            c.drawString(x, y, line)
            y -= leading
            line = w
        else:
            line = trial
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def render_pdf(db, req, cert, s) -> bytes:
    import segno
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    _fonts()
    navy, grey, red = HexColor("#14213d"), HexColor("#5b6475"), HexColor("#b3261e")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Справка {cert['number']}")
    c.setAuthor("Цифровой деканат — концепт")
    w, h = A4
    x0 = 22 * mm
    # шапка
    c.setFillColor(navy)
    c.rect(0, h - 28 * mm, w, 28 * mm, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("PTSans-Bold", 13)
    c.drawString(x0, h - 14 * mm, "ЦИФРОВОЙ ДЕКАНАТ")
    c.setFont("PTSans", 9.5)
    c.drawString(x0, h - 20 * mm, "Концепт для конкурса «Цифровой деканат будущего». Не официальный документ МГИМО.")
    # водяной знак
    c.saveState()
    c.setFillColor(HexColor("#e9ecf2"))
    c.setFont("PTSans-Bold", 34)
    c.translate(w / 2, h / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, "ОБРАЗЕЦ · ДАННЫЕ ВЫМЫШЛЕНЫ")
    c.restoreState()
    y = h - 46 * mm
    c.setFillColor(navy)
    c.setFont("PTSans-Bold", 18)
    c.drawString(x0, y, req["title"].upper() if req["type_code"] != "study_cert" else "СПРАВКА ОБ ОБУЧЕНИИ")
    y -= 8 * mm
    c.setFont("PTSans", 10.5)
    c.setFillColor(grey)
    issued = cert["issued_at"].astimezone(MSK)
    c.drawString(x0, y, f"№ {cert['number']} от {human_date(issued.date())} {issued.year} г. · по заявке № {req['number']}")
    y -= 14 * mm
    c.setFillColor(HexColor("#111111"))
    c.setFont("PTSans", 12)
    fio = f"{s['last_name']} {s['first_name']} {s['middle_name']}".strip()
    form = "за счёт бюджетных ассигнований" if s["funding"] == "budget" else "по договору об оказании платных образовательных услуг"
    female = (s["middle_name"] or "").endswith(("вна", "чна", "кызы"))
    who = "действительно является студенткой" if female else "действительно является студентом"
    text = (f"Настоящая справка подтверждает, что {fio} {who} {s['course']}-го курса очной формы обучения, "
            f"{s['faculty_name'].lower()}, направление подготовки {s['program']}, профиль «{s['profile']}», группа {s['group_code']}, "
            f"обучается {form}. Год поступления — {s['enrolled_year']}. Номер зачётной книжки {s['record_book']}.")
    y = _wrap(c, text, x0, y, w - 2 * x0, "PTSans", 12, 17)
    y -= 6
    purpose = next((v for k, v in (req["payload"] or {}).items() if k in ("purpose", "organization", "commissariat")), "по месту требования")
    low = purpose[:1].lower() + purpose[1:]
    if low.startswith("для "):
        line = f"Справка выдана {low}."
    elif low.startswith(("в ", "по ")):
        line = f"Справка выдана для предъявления {low}."
    else:
        line = f"Справка выдана для предъявления: {purpose}."
    y = _wrap(c, line, x0, y, w - 2 * x0, "PTSans", 12, 17)
    y -= 4
    y = _wrap(c, f"Действительна до {cert['valid_until']:%d.%m.%Y}.", x0, y, w - 2 * x0, "PTSans", 12, 17)
    # QR и проверка
    qr = segno.make(verify_url(cert["verify_code"]), error="m")
    png = io.BytesIO()
    qr.save(png, kind="png", scale=6, border=1, dark="#14213d")
    png.seek(0)
    box_y = 40 * mm
    c.setStrokeColor(HexColor("#d5d9e2"))
    c.roundRect(x0, box_y, w - 2 * x0, 42 * mm, 6, stroke=1, fill=0)
    c.drawImage(ImageReader(png), x0 + 5 * mm, box_y + 5 * mm, 32 * mm, 32 * mm)
    c.setFont("PTSans-Bold", 11)
    c.setFillColor(navy)
    c.drawString(x0 + 44 * mm, box_y + 30 * mm, "Проверка подлинности")
    c.setFont("PTSans", 10)
    c.setFillColor(grey)
    c.drawString(x0 + 44 * mm, box_y + 23 * mm, "Наведите камеру на QR-код или откройте адрес:")
    c.setFillColor(HexColor("#111111"))
    c.setFont("PTSans", 9)
    c.drawString(x0 + 44 * mm, box_y + 17 * mm, verify_url(cert["verify_code"]))
    c.setFillColor(grey)
    c.setFont("PTSans", 9)
    c.drawString(x0 + 44 * mm, box_y + 9 * mm, "В действующей системе документ подписывается усиленной квалифицированной")
    c.drawString(x0 + 44 * mm, box_y + 5 * mm, "электронной подписью (63-ФЗ); здесь подписи нет — это образец.")
    c.setFillColor(red)
    c.setFont("PTSans-Bold", 9)
    c.drawString(x0, 22 * mm, "ОБРАЗЕЦ ДЛЯ КОНКУРСА. ВСЕ ДАННЫЕ ВЫМЫШЛЕНЫ. НЕ ЯВЛЯЕТСЯ ОФИЦИАЛЬНЫМ ДОКУМЕНТОМ.")
    c.showPage()
    c.save()
    return buf.getvalue()


def mask_name(last, first, middle):
    return f"{last[0]}{'*' * max(2, len(last) - 1)} {first[0]}. {(middle[0] + '.') if middle else ''}".strip()


@router.get("/api/verify/{code}")
def verify(request: Request, code: str = PathParam(pattern=r"^[A-Za-z0-9_-]{10,40}$"), db=Depends(database)):
    """публичная проверка справки по коду из QR: минимум сведений, без персональных данных"""
    ratelimit.hit(db, f"feed:{client_ip(request)}")
    row = db.execute("""SELECT c.*, t.title, s.last_name, s.first_name, s.middle_name, f.name AS faculty
        FROM certificates c JOIN requests r ON r.id = c.request_id JOIN request_types t ON t.code = r.type_code
        JOIN students s ON s.user_id = r.student_id JOIN faculties f ON f.id = s.faculty_id WHERE c.verify_code=%s""", (code,)).fetchone()
    if not row:
        raise ApiError(404, "Документ с таким кодом не найден")
    today = datetime.now(MSK).date()
    valid = row["revoked_at"] is None and (row["valid_until"] is None or row["valid_until"] >= today)
    return {"valid": valid, "number": row["number"], "title": row["title"], "issued_at": row["issued_at"], "valid_until": row["valid_until"],
            "holder": mask_name(row["last_name"], row["first_name"], row["middle_name"]), "faculty": row["faculty"],
            "revoked": row["revoked_at"] is not None, "note": "Концепт для конкурса: документ-образец с вымышленными данными"}
