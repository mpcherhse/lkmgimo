"""Заявки: статусы, переходы, номера, справки с QR-проверкой."""
import secrets
from datetime import datetime, timedelta


STATUS_TEXT = {"submitted": "Подана", "accepted": "Принята", "in_progress": "В работе", "ready": "Готова",
               "done": "Выдана", "rejected": "Отклонена", "cancelled": "Отозвана"}
# кто куда может перевести заявку
STAFF_FLOW = {"submitted": {"accepted", "rejected"}, "accepted": {"in_progress", "ready", "rejected"},
              "in_progress": {"ready", "rejected"}, "ready": {"done"}}


def next_statuses(status, category):
    """вопрос в деканат закрывается ответом сразу, документ — только через «Готова»"""
    allowed = set(STAFF_FLOW.get(status, set()))
    if category == "question" and status in OPEN:
        allowed |= {"done"}
        allowed.discard("ready")
    return allowed
OPEN = {"submitted", "accepted", "in_progress", "ready"}


def request_number(conn):
    n = conn.execute("SELECT count(*) AS n FROM requests").fetchone()["n"] + 1
    return f"З-{datetime.now().year}-{n:05d}"


def add_event(conn, request_id, status, message, role, name="", at=None):
    conn.execute("""INSERT INTO request_events (request_id, at, status, message, author_role, author_name)
        VALUES (%s, coalesce(%s, now()), %s, %s, %s, %s)""", (request_id, at, status, message or "", role, name))


def make_certificate(conn, request_id, issued_at=None):
    """электронная справка: номер и случайный код проверки (по нему QR ведёт на страницу подлинности)"""
    row = conn.execute("SELECT id FROM certificates WHERE request_id=%s", (request_id,)).fetchone()
    if row:
        return row["id"]
    n = conn.execute("SELECT count(*) AS n FROM certificates").fetchone()["n"] + 1
    issued_at = issued_at or datetime.now().astimezone()
    return conn.execute("""INSERT INTO certificates (request_id, number, verify_code, issued_at, valid_until)
        VALUES (%s, %s, %s, %s, %s) RETURNING id""", (request_id, f"С-{issued_at:%Y}-{n:05d}", secrets.token_urlsafe(12), issued_at,
                                                    (issued_at + timedelta(days=90)).date())).fetchone()["id"]


def validate_payload(fields, payload):
    """тело заявки строго по описанию полей типа: лишнее отбрасываем, обязательное проверяем, длину ограничиваем"""
    from .web import ApiError
    if not isinstance(payload, dict):
        raise ApiError(422, "Неверный формат заявки")
    unknown = set(payload) - {f["name"] for f in fields}
    if unknown:
        raise ApiError(422, "Лишние поля в заявке", fields=sorted(unknown))
    clean = {}
    for f in fields:
        v = payload.get(f["name"])
        if v is None or (isinstance(v, str) and not v.strip()):
            if f.get("required"):
                raise ApiError(422, f"Заполните поле «{f['label']}»", field=f["name"])
            continue
        if not isinstance(v, str):
            raise ApiError(422, f"Поле «{f['label']}» должно быть строкой", field=f["name"])
        v = v.strip()
        if f["type"] == "select" and v not in f["options"]:
            raise ApiError(422, f"Выберите значение из списка в поле «{f['label']}»", field=f["name"])
        if f["type"] == "date":
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ApiError(422, f"Неверная дата в поле «{f['label']}»", field=f["name"]) from None
        limit = f.get("max", 200)
        if len(v) > limit:
            raise ApiError(422, f"Поле «{f['label']}» длиннее {limit} символов", field=f["name"])
        if any(ord(ch) < 32 and ch not in "\n\t" for ch in v):
            raise ApiError(422, f"В поле «{f['label']}» есть служебные символы", field=f["name"])
        clean[f["name"]] = v
    return clean
