"""API студента. Каждый запрос ограничен пользователем сеанса: чужие записи не видны и на запрос по чужому id отвечают 404,
как будто записи нет (не подсказываем, что она существует)."""
import json
from urllib.parse import quote
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from pydantic import Field

from . import grading, ratelimit
from .auth.routes import Strict, current_user, student_user
from .requests_logic import OPEN, STATUS_TEXT, status_label, add_event, request_number, validate_payload
from .schedule_changes import change_text
from .security import public_id
from .timetable import MSK, PAIRS, WEEKDAYS, human_date, now_msk, today, week_no
from .web import ApiError, audit, database, mutation

router = APIRouter()
PID = Path(pattern=r"^[A-Za-z0-9_-]{8,32}$")
KIND_TEXT = {"lecture": "Лекция", "seminar": "Семинар", "language": "Иностранный язык", "consult": "Консультация", "exam": "Экзамен",
             "zachet": "Зачёт", "event": "Мероприятие"}


# ---------- общие выборки ----------
def student(db, uid):
    s = db.execute("""SELECT s.*, f.code AS faculty_code, f.name AS faculty_name, f.pair_scheme, f.dean_office, f.dean_phone, f.dean_email,
        g.code AS group_code FROM students s JOIN faculties f ON f.id = s.faculty_id JOIN groups g ON g.id = s.group_id
        WHERE s.user_id = %s""", (uid,)).fetchone()
    if not s:
        raise ApiError(404, "Профиль студента не найден")
    s["languages"] = db.execute("""SELECT g.id, g.code, g.language FROM student_language_groups l JOIN groups g ON g.id = l.group_id
        WHERE l.student_id = %s ORDER BY g.code""", (uid,)).fetchall()
    s["group_ids"] = [s["group_id"]] + [g["id"] for g in s["languages"]]
    return s


def current_semester(db):
    return db.execute("SELECT * FROM semesters WHERE is_current").fetchone()


def lesson_view(r):
    st = r["starts_at"].astimezone(MSK)
    en = r["ends_at"].astimezone(MSK)
    out = {"id": r["public_id"], "discipline": r["discipline"], "kind": r["kind"], "kind_text": KIND_TEXT.get(r["kind"], r["kind"]),
           "date": st.date().isoformat(), "start": f"{st:%H:%M}", "end": f"{en:%H:%M}", "pair": r["pair_no"],
           "teacher": f"{r['teacher_title']} {r['teacher']}".strip() if r.get("teacher") else "",
           "room": r["room"], "building": r["building"], "online_url": r["online_url"], "status": r["status"],
           "groups": r.get("groups") or [], "change": None}
    if r["status"] != "ok":
        title, body = change_text(r, r["discipline"])
        prev = None
        if r.get("prev_starts_at"):
            ps = r["prev_starts_at"].astimezone(MSK)
            prev = {"date": ps.date().isoformat(), "start": f"{ps:%H:%M}", "room": r.get("prev_room")}
        out["change"] = {"title": title, "text": body, "reason": r["change_reason"], "at": r["changed_at"], "prev": prev}
    return out


LESSON_SQL = """SELECT l.*, d.name AS discipline, t.full_name AS teacher, t.title AS teacher_title,
    (SELECT array_agg(g.code ORDER BY g.code) FROM groups g WHERE g.id = ANY(l.group_ids)) AS groups
    FROM lessons l JOIN disciplines d ON d.id = l.discipline_id LEFT JOIN teachers t ON t.id = l.teacher_id"""


def lessons_between(db, group_ids, start: datetime, end: datetime, kinds=None):
    rows = db.execute(LESSON_SQL + """ WHERE l.group_ids && %s::int[] AND l.starts_at < %s AND l.ends_at > %s
        AND (%s::text[] IS NULL OR l.kind = ANY(%s::text[])) ORDER BY l.starts_at, d.name""",
                      (group_ids, end, start, kinds, kinds)).fetchall()
    return [lesson_view(r) for r in rows]


def deadlines_for(db, s, start, end):
    rows = db.execute("""SELECT * FROM deadlines WHERE due_at >= %s AND due_at < %s
        AND (student_id = %s OR (student_id IS NULL AND (group_ids && %s::int[] OR (group_ids IS NULL AND faculty_id = %s))))
        ORDER BY due_at""", (start, end, s["user_id"], s["group_ids"], s["faculty_id"])).fetchall()
    return [{"id": r["public_id"], "title": r["title"], "details": r["details"], "due_at": r["due_at"], "kind": r["kind"]} for r in rows]


def _day_start(d: date):
    return datetime(d.year, d.month, d.day, tzinfo=MSK)


# ---------- профиль ----------
@router.get("/api/me")
def me(user=Depends(current_user), db=Depends(database)):
    s = user["session"]
    out = {"login": user["login"], "role": user["role"], "demo": user["demo"], "totp_enabled": user["totp_enabled"],
           "sudo_until": s["sudo_until"], "session_id": s["public_id"],
           "unread": db.execute("SELECT count(*) AS n FROM notifications WHERE user_id=%s AND read_at IS NULL", (user["id"],)).fetchone()["n"]}
    if user["role"] == "student":
        st = student(db, user["id"])
        out["name"] = {"last": st["last_name"], "first": st["first_name"], "middle": st["middle_name"]}
        out["short"] = f"{st['first_name']} {st['last_name']}"
        out["faculty"] = st["faculty_code"]
        out["group"] = st["group_code"]
        out["course"] = st["course"]
    else:
        row = db.execute("SELECT full_name, position FROM staff WHERE user_id=%s", (user["id"],)).fetchone()
        out["short"] = row["full_name"]
        out["position"] = row["position"]
        out["faculties"] = [r["code"] for r in db.execute("""SELECT f.code FROM staff_faculties sf JOIN faculties f ON f.id = sf.faculty_id
            WHERE sf.staff_id=%s ORDER BY f.code""", (user["id"],))]
    return out


@router.get("/api/profile")
def profile(user=Depends(student_user), db=Depends(database)):
    s = student(db, user["id"])
    return {"last_name": s["last_name"], "first_name": s["first_name"], "middle_name": s["middle_name"],
            "faculty": {"code": s["faculty_code"], "name": s["faculty_name"]}, "program": s["program"], "profile": s["profile"],
            "level": s["level"], "course": s["course"], "group": s["group_code"],
            "languages": [{"code": g["code"], "language": g["language"]} for g in s["languages"]],
            "record_book": s["record_book"], "funding": "Бюджет" if s["funding"] == "budget" else "Договор", "email": s["email"],
            "phone": s["phone"], "enrolled_year": s["enrolled_year"], "advisor": s["advisor"],
            "dean": {"office": s["dean_office"], "phone": s["dean_phone"], "email": s["dean_email"]}}


# ---------- главная ----------
@router.get("/api/dashboard")
def dashboard(user=Depends(student_user), db=Depends(database)):
    s = student(db, user["id"])
    sem = current_semester(db)
    now = now_msk()
    d = now.date()
    todays = lessons_between(db, s["group_ids"], _day_start(d), _day_start(d + timedelta(days=1)))
    upcoming = [x for x in todays if x["status"] != "cancelled" and x["end"] > f"{now:%H:%M}"]
    nxt = upcoming[0] if upcoming else None
    if not nxt:
        later = lessons_between(db, s["group_ids"], _day_start(d + timedelta(days=1)), _day_start(d + timedelta(days=8)))
        nxt = next((x for x in later if x["status"] != "cancelled"), None)
    changes = [x for x in lessons_between(db, s["group_ids"], _day_start(d), _day_start(d + timedelta(days=8))) if x["status"] != "ok"]
    deadlines = deadlines_for(db, s, now, now + timedelta(days=21))
    reqs = db.execute("""SELECT r.public_id, r.number, r.status, r.updated_at, t.title, t.category FROM requests r JOIN request_types t ON t.code = r.type_code
        WHERE r.student_id=%s AND (r.status = ANY(%s) OR r.updated_at > now() - interval '3 days') ORDER BY r.updated_at DESC LIMIT 5""",
                      (user["id"], list(OPEN))).fetchall()
    notes = db.execute("""SELECT public_id, kind, title, body, important, created_at FROM notifications
        WHERE user_id=%s AND read_at IS NULL ORDER BY important DESC, created_at DESC LIMIT 4""", (user["id"],)).fetchall()
    g = grades_payload(db, s, sem["code"])
    return {
        "today": {"date": d.isoformat(), "weekday": WEEKDAYS[d.weekday()], "human": human_date(d),
                  "week": week_no(d, sem["starts_on"]) if sem["starts_on"] <= d <= sem["ends_on"] else None,
                  "parity": ("нечётная" if week_no(d, sem["starts_on"]) % 2 else "чётная") if sem["starts_on"] <= d <= sem["ends_on"] else None,
                  "lessons": todays},
        "next": nxt, "changes": changes, "deadlines": deadlines,
        "requests": [{"id": r["public_id"], "number": r["number"], "title": r["title"], "status": r["status"],
                      "status_text": status_label(r["status"], r["category"]), "updated_at": r["updated_at"]} for r in reqs],
        "notifications": [{"id": n["public_id"], "kind": n["kind"], "title": n["title"], "body": n["body"], "important": n["important"],
                           "created_at": n["created_at"]} for n in notes],
        "rating": {"semester": sem["title"], "estimate": g["summary"]["estimate"], "estimate_grade": g["summary"]["estimate_grade"],
                   "previous": g["history"][-1] if g["history"] else None, "attention": g["attention"]},
        "session": {"from": sem["session_from"], "to": sem["session_to"], "days_left": (sem["session_from"] - d).days},
    }


# ---------- расписание ----------
@router.get("/api/schedule")
def schedule(start: date = Query(None, alias="from"), days: int = Query(7, ge=1, le=31), user=Depends(student_user), db=Depends(database)):
    s = student(db, user["id"])
    sem = current_semester(db)
    start = start or (today() - timedelta(days=today().weekday()))
    items = lessons_between(db, s["group_ids"], _day_start(start), _day_start(start + timedelta(days=days)))
    out_days = []
    for i in range(days):
        d = start + timedelta(days=i)
        wk = week_no(d, sem["starts_on"]) if sem["starts_on"] <= d <= sem["session_to"] else None
        out_days.append({"date": d.isoformat(), "weekday": WEEKDAYS[d.weekday()], "human": human_date(d), "week": wk,
                         "parity": ("нечётная" if wk and wk % 2 else "чётная") if wk else None,
                         "lessons": [x for x in items if x["date"] == d.isoformat()]})
    scheme = s["pair_scheme"]
    pairs = [{"n": i + 1, "start": a, "end": b} for i, (a, b) in enumerate(PAIRS[scheme])]
    return {"from": start.isoformat(), "days": out_days, "pairs": pairs, "today": today().isoformat(),
            "semester": {"title": sem["title"], "starts_on": sem["starts_on"], "ends_on": sem["ends_on"]}}


@router.get("/api/session")
def session_schedule(user=Depends(student_user), db=Depends(database)):
    s = student(db, user["id"])
    sem = current_semester(db)
    items = lessons_between(db, s["group_ids"], _day_start(sem["ends_on"] - timedelta(days=10)), _day_start(sem["session_to"] + timedelta(days=1)),
                            kinds=["zachet", "consult", "exam"])
    return {"semester": sem["title"], "from": sem["session_from"], "to": sem["session_to"], "items": items}


# ---------- успеваемость ----------
def grades_payload(db, s, sem_code):
    sems = db.execute("""SELECT DISTINCT se.* FROM semesters se JOIN offerings o ON o.semester_id = se.id
        JOIN grade_records g ON g.offering_id = o.id WHERE g.student_id = %s ORDER BY se.starts_on""", (s["user_id"],)).fetchall()
    if not sems:
        sems = [current_semester(db)]
    chosen = next((x for x in sems if x["code"] == sem_code), sems[-1])
    history, retakes_any = [], False
    for se in sems:
        rows = db.execute("""SELECT g.*, o.control, d.name AS discipline, t.full_name AS teacher, t.title AS teacher_title
            FROM grade_records g JOIN offerings o ON o.id = g.offering_id JOIN disciplines d ON d.id = o.discipline_id
            LEFT JOIN teachers t ON t.id = o.teacher_id WHERE g.student_id=%s AND o.semester_id=%s ORDER BY d.name""",
                          (s["user_id"], se["id"])).fetchall()
        bonus = db.execute("SELECT bonus FROM semester_bonuses WHERE student_id=%s AND semester_id=%s", (s["user_id"], se["id"])).fetchone()
        summary = grading.semester([(r, r["control"]) for r in rows], bonus["bonus"] if bonus else 0)
        retakes_any = retakes_any or any(r["retakes"] for r in rows)
        if summary["complete"]:
            history.append({"code": se["code"], "title": se["title"], "rating": summary["rating"], "grade": summary["grade"],
                            "bonus": summary["bonus"]})
        if se["id"] == chosen["id"]:
            chosen_rows, chosen_summary = rows, summary
    disciplines, attention = [], []
    for r in chosen_rows:
        d = grading.discipline(r, r["control"])
        item = {"discipline": r["discipline"], "teacher": f"{r['teacher_title']} {r['teacher']}".strip() if r["teacher"] else "",
                "control": r["control"], "control_text": "Экзамен" if r["control"] == "exam" else "Зачёт", **d}
        disciplines.append(item)
        if chosen["is_current"] and d["b1"] is not None and d["b1"] < 70:
            attention.append({"discipline": r["discipline"], "b1": d["b1"], "control": r["control"],
                              "text": ("Ниже 70%: автоматического зачёта не будет, зачёт сдаётся, оценка за него не выше 69%"
                                       if r["control"] == "zachet" else "Ниже 70% по текущему контролю: стоит подтянуть 3-й срез")})
    out = {"semesters": [{"code": x["code"], "title": x["title"], "current": x["is_current"]} for x in sems],
           "semester": {"code": chosen["code"], "title": chosen["title"], "current": chosen["is_current"]},
           "summary": chosen_summary, "disciplines": disciplines, "history": history, "attention": attention,
           "scale": [{"from": e, "letter": l, "five": f, "word": w} for e, l, f, w in grading.SCALE],
           "weights": {"b1": grading.W1, "b2": grading.W2, "b3": grading.W3}}
    if s["funding"] == "contract":
        out["discount"] = grading.tuition_discount([h["rating"] for h in history], retakes_any)
    return out


@router.get("/api/grades")
def grades(semester: str = Query(None, pattern=r"^\d{4}-[12]$"), user=Depends(student_user), db=Depends(database)):
    s = student(db, user["id"])
    return grades_payload(db, s, semester)


# ---------- дедлайны ----------
@router.get("/api/deadlines")
def deadlines(user=Depends(student_user), db=Depends(database)):
    s = student(db, user["id"])
    now = now_msk()
    return {"items": deadlines_for(db, s, now - timedelta(days=1), now + timedelta(days=120))}


# ---------- заявки ----------
def _type_view(t):
    return {"code": t["code"], "title": t["title"], "category": t["category"], "description": t["description"], "days": t["days"],
            "fields": t["fields"], "electronic": t["electronic"]}


@router.get("/api/request-types")
def request_types(user=Depends(student_user), db=Depends(database)):
    return {"items": [_type_view(t) for t in db.execute("SELECT * FROM request_types ORDER BY sort")]}


def _own_request(db, uid, pid):
    r = db.execute("""SELECT r.*, t.title, t.category, t.electronic, t.days, t.fields FROM requests r JOIN request_types t ON t.code = r.type_code
        WHERE r.public_id=%s AND r.student_id=%s""", (pid, uid)).fetchone()
    if not r:
        raise ApiError(404, "Заявка не найдена")
    return r


def request_view(db, r, full=False):
    out = {"id": r["public_id"], "number": r["number"], "type": r["type_code"], "title": r["title"], "category": r["category"],
           "status": r["status"], "status_text": status_label(r["status"], r["category"]), "status_comment": r["status_comment"],
           "delivery": r["delivery"], "created_at": r["created_at"], "updated_at": r["updated_at"], "due_on": r["due_on"],
           "can_cancel": r["status"] == "submitted"}
    cert = db.execute("SELECT number, verify_code, issued_at, valid_until, revoked_at FROM certificates WHERE request_id=%s", (r["id"],)).fetchone()
    out["document"] = {"number": cert["number"], "issued_at": cert["issued_at"], "valid_until": cert["valid_until"]} if cert else None
    if full:
        fields = {f["name"]: f["label"] for f in r["fields"]}
        out["payload"] = [{"label": fields.get(k, k), "value": v} for k, v in (r["payload"] or {}).items()]
        out["events"] = [{"at": e["at"], "status": e["status"], "status_text": status_label(e["status"], r["category"]) if e["status"] else None,
                          "message": e["message"], "author": e["author_role"], "author_name": e["author_name"]}
                         for e in db.execute("SELECT * FROM request_events WHERE request_id=%s ORDER BY at, id", (r["id"],))]
    return out


@router.get("/api/requests")
def my_requests(user=Depends(student_user), db=Depends(database)):
    rows = db.execute("""SELECT r.*, t.title, t.category, t.electronic, t.days, t.fields FROM requests r JOIN request_types t ON t.code = r.type_code
        WHERE r.student_id=%s ORDER BY r.created_at DESC""", (user["id"],)).fetchall()
    return {"items": [request_view(db, r) for r in rows]}


class RequestIn(Strict):
    type: str = Field(min_length=1, max_length=40)
    delivery: str = Field(pattern=r"^(electronic|paper)$")
    payload: dict


@router.post("/api/requests", dependencies=[Depends(mutation)])
def create_request(data: RequestIn, user=Depends(student_user), db=Depends(database)):
    ratelimit.hit(db, f"request_create:{user['id']}", message="Слишком много заявок за час. Попробуйте позже")
    t = db.execute("SELECT * FROM request_types WHERE code=%s", (data.type,)).fetchone()
    if not t:
        raise ApiError(422, "Такого типа заявки нет")
    if data.delivery == "electronic" and not t["electronic"] and t["category"] != "question":
        raise ApiError(422, "Этот документ выдаётся только на бумаге")
    if len(json.dumps(data.payload, ensure_ascii=False)) > 8000:
        raise ApiError(413, "Слишком большая заявка")
    payload = validate_payload(t["fields"], data.payload)
    s = student(db, user["id"])
    with db.transaction():
        db.execute("SELECT pg_advisory_xact_lock(4242)")   # номер заявки выдаётся по порядку без гонок
        rid = db.execute("""INSERT INTO requests (public_id, number, student_id, type_code, payload, delivery, status, due_on)
            VALUES (%s, %s, %s, %s, %s, %s, 'submitted', %s) RETURNING id""",
                         (public_id(), request_number(db), user["id"], t["code"], json.dumps(payload, ensure_ascii=False),
                          "electronic" if t["category"] == "question" else data.delivery,
                          today() + timedelta(days=t["days"] + (t["days"] // 5) * 2))).fetchone()["id"]
        add_event(db, rid, "submitted", "", "student", f"{s['first_name']} {s['last_name']}")
        audit(db, user["id"], "request.create", t["code"])
    return request_view(db, _own_request(db, user["id"], db.execute("SELECT public_id FROM requests WHERE id=%s", (rid,)).fetchone()["public_id"]), full=True)


@router.get("/api/requests/{pid}")
def get_request(pid: str = PID, user=Depends(student_user), db=Depends(database)):
    return request_view(db, _own_request(db, user["id"], pid), full=True)


@router.post("/api/requests/{pid}/cancel", dependencies=[Depends(mutation)])
def cancel_request(pid: str = PID, user=Depends(student_user), db=Depends(database)):
    r = _own_request(db, user["id"], pid)
    with db.transaction():
        n = db.execute("UPDATE requests SET status='cancelled', updated_at=now() WHERE id=%s AND status='submitted'", (r["id"],)).rowcount
        if not n:
            raise ApiError(409, "Отозвать можно только заявку, которую деканат ещё не принял")
        add_event(db, r["id"], "cancelled", "Отозвана студентом", "student")
    return request_view(db, _own_request(db, user["id"], pid), full=True)


class MessageIn(Strict):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/api/requests/{pid}/messages", dependencies=[Depends(mutation)])
def request_message(data: MessageIn, pid: str = PID, user=Depends(student_user), db=Depends(database)):
    r = _own_request(db, user["id"], pid)
    if r["status"] not in OPEN:
        raise ApiError(409, "Заявка закрыта — создайте новую")
    s = student(db, user["id"])
    with db.transaction():
        add_event(db, r["id"], None, data.text.strip(), "student", f"{s['first_name']} {s['last_name']}")
        db.execute("UPDATE requests SET updated_at=now() WHERE id=%s", (r["id"],))
    return request_view(db, _own_request(db, user["id"], pid), full=True)


@router.get("/api/requests/{pid}/document.pdf")
def request_document(pid: str = PID, user=Depends(student_user), db=Depends(database)):
    from .certificates import render_pdf
    r = _own_request(db, user["id"], pid)
    cert = db.execute("SELECT * FROM certificates WHERE request_id=%s AND revoked_at IS NULL", (r["id"],)).fetchone()
    if not cert:
        raise ApiError(404, "Документ ещё не готов")
    pdf = render_pdf(db, r, cert, student(db, user["id"]))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=\"spravka.pdf\"; filename*=UTF-8''{quote('Справка ' + cert['number'] + '.pdf')}",
                             "Cache-Control": "no-store"})


# ---------- уведомления ----------
@router.get("/api/notifications")
def notifications(unread: bool = False, kind: str = Query(None, pattern=r"^(announcement|schedule|request|deadline|grade|security)$"),
                  q: str = Query(None, max_length=100), limit: int = Query(50, ge=1, le=200), user=Depends(current_user), db=Depends(database)):
    like = f"%{q.strip()}%" if q and q.strip() else None
    rows = db.execute("""SELECT * FROM notifications WHERE user_id=%s AND (%s = false OR read_at IS NULL) AND (%s::text IS NULL OR kind = %s)
        AND (%s::text IS NULL OR title COLLATE \"und-x-icu\" ILIKE %s OR body COLLATE \"und-x-icu\" ILIKE %s) ORDER BY created_at DESC LIMIT %s""",
                      (user["id"], unread, kind, kind, like, like, like, limit)).fetchall()
    counts = db.execute("""SELECT kind, count(*) FILTER (WHERE read_at IS NULL) AS unread, count(*) AS total FROM notifications
        WHERE user_id=%s GROUP BY kind""", (user["id"],)).fetchall()
    return {"items": [{"id": r["public_id"], "kind": r["kind"], "title": r["title"], "body": r["body"], "link": r["link"],
                       "important": r["important"], "created_at": r["created_at"], "read": r["read_at"] is not None} for r in rows],
            "counts": {c["kind"]: {"unread": c["unread"], "total": c["total"]} for c in counts}}


@router.post("/api/notifications/{pid}/read", dependencies=[Depends(mutation)])
def notification_read(pid: str = PID, user=Depends(current_user), db=Depends(database)):
    n = db.execute("UPDATE notifications SET read_at=coalesce(read_at, now()) WHERE public_id=%s AND user_id=%s", (pid, user["id"])).rowcount
    if not n:
        raise ApiError(404, "Уведомление не найдено")
    return {"ok": True}


@router.post("/api/notifications/read-all", dependencies=[Depends(mutation)])
def notifications_read_all(user=Depends(current_user), db=Depends(database)):
    n = db.execute("UPDATE notifications SET read_at=now() WHERE user_id=%s AND read_at IS NULL", (user["id"],)).rowcount
    return {"ok": True, "count": n}


# ---------- поиск по кабинету ----------
@router.get("/api/search")
def search(q: str = Query(min_length=2, max_length=60), user=Depends(student_user), db=Depends(database)):
    s = student(db, user["id"])
    like = f"%{q.strip()}%"
    disc = db.execute("""SELECT DISTINCT d.name FROM lessons l JOIN disciplines d ON d.id=l.discipline_id
        WHERE l.group_ids && %s::int[] AND d.name COLLATE \"und-x-icu\" ILIKE %s LIMIT 5""", (s["group_ids"], like)).fetchall()
    types = db.execute("SELECT code, title FROM request_types WHERE title COLLATE \"und-x-icu\" ILIKE %s OR description COLLATE \"und-x-icu\" ILIKE %s ORDER BY sort LIMIT 5", (like, like)).fetchall()
    notes = db.execute("""SELECT public_id, title FROM notifications WHERE user_id=%s AND (title COLLATE \"und-x-icu\" ILIKE %s OR body COLLATE \"und-x-icu\" ILIKE %s)
        ORDER BY created_at DESC LIMIT 5""", (user["id"], like, like)).fetchall()
    return {"disciplines": [d["name"] for d in disc], "request_types": [{"code": t["code"], "title": t["title"]} for t in types],
            "notifications": [{"id": n["public_id"], "title": n["title"]} for n in notes]}
