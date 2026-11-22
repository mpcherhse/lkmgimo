"""Календари.
1) Ссылка-подписка (ICS, RFC 5545): /cal/<секретный токен>.ics — для iPhone/Mac (webcal://), Google Календаря (Android),
   Яндекс Календаря, Outlook. Токен случайный, в базе только SHA-256; ссылку можно перевыпустить — старая перестанет работать.
2) CalDAV только для чтения (app/caldav.py) — для HarmonyOS («Добавить CalDAV-календарь»), iOS/macOS (аккаунт CalDAV), Android (DAVx⁵).
   Вход — логин и пароль приложения (не основной пароль): его видно один раз, отзывается в кабинете.
Перенос занятия увеличивает SEQUENCE и LAST-MODIFIED — календари телефона обновляют событие, а не дублируют его."""
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import Response
from icalendar import Alarm, Calendar, Event
from pydantic import Field

from . import config, ratelimit
from .auth import clock
from .auth.routes import Strict, student_user, sudo_user
from .routes_student import KIND_TEXT, LESSON_SQL, current_semester, student
from .schedule_changes import change_text
from .security import app_password, new_token, public_id, token_hash
from .timetable import MSK
from .web import ApiError, audit, client_ip, database, mutation, rate_ip

router = APIRouter()
PRODID = "-//Tsifrovoy dekanat (concept)//LK//RU"
UID_DOMAIN = "lk-concept"


# ---------- данные для календаря ----------
def calendar_rows(db, s):
    sem = current_semester(db)
    start = datetime(sem["starts_on"].year, sem["starts_on"].month, sem["starts_on"].day, tzinfo=MSK)
    end = datetime(sem["session_to"].year, sem["session_to"].month, sem["session_to"].day, tzinfo=MSK) + timedelta(days=1)
    lessons = db.execute(LESSON_SQL + " WHERE l.group_ids && %s::int[] AND l.starts_at >= %s AND l.starts_at < %s ORDER BY l.starts_at",
                         (s["group_ids"], start, end)).fetchall()
    deadlines = db.execute("""SELECT * FROM deadlines WHERE due_at >= %s
        AND (student_id = %s OR (student_id IS NULL AND (group_ids && %s::int[] OR (group_ids IS NULL AND faculty_id = %s))))
        ORDER BY due_at""", (start, s["user_id"], s["group_ids"], s["faculty_id"])).fetchall()
    return lessons, deadlines


def lesson_uid(r):
    return f"lesson-{r['public_id']}@{UID_DOMAIN}"


def deadline_uid(r):
    return f"deadline-{r['public_id']}@{UID_DOMAIN}"


def lesson_event(r) -> Event:
    e = Event()
    e.add("uid", lesson_uid(r))
    e.add("dtstamp", r["updated_at"])
    e.add("last-modified", r["updated_at"])
    e.add("sequence", r["sequence"])
    e.add("dtstart", r["starts_at"].astimezone(MSK))
    e.add("dtend", r["ends_at"].astimezone(MSK))
    kind = KIND_TEXT.get(r["kind"], "")
    title = f"{r['discipline']} · {kind}" if r["kind"] not in ("exam", "zachet") else f"{kind}: {r['discipline']}"
    if r["status"] == "cancelled":
        title = "ОТМЕНА — " + title
    elif r["status"] == "moved":
        title = "Изменение — " + title
    e.add("summary", title)
    if r["online_url"]:
        e.add("location", "Онлайн")
        e.add("url", r["online_url"])
    elif r["room"]:
        e.add("location", f"ауд. {r['room']}, {r['building']}".strip(", "))
    lines = []
    if r.get("teacher"):
        lines.append(f"Преподаватель: {r['teacher_title']} {r['teacher']}".strip())
    if r["pair_no"]:
        lines.append(f"{r['pair_no']}-я пара")
    if r["status"] != "ok":
        lines.append(change_text(r, r["discipline"])[1])
    if r["online_url"]:
        lines.append(f"Ссылка: {r['online_url']}")
    lines.append("Концепт для конкурса, данные вымышлены.")
    e.add("description", "\n".join(lines))
    e.add("status", "CANCELLED" if r["status"] == "cancelled" else "CONFIRMED")
    e.add("categories", [kind])
    e.add("transp", "TRANSPARENT" if r["status"] == "cancelled" else "OPAQUE")
    if r["kind"] in ("exam", "zachet") and r["status"] != "cancelled":
        for trigger in (timedelta(days=-1), timedelta(hours=-2)):
            a = Alarm()
            a.add("action", "DISPLAY")
            a.add("description", title)
            a.add("trigger", trigger)
            e.add_component(a)
    return e


def deadline_event(r) -> Event:
    e = Event()
    e.add("uid", deadline_uid(r))
    e.add("dtstamp", r["updated_at"])
    e.add("last-modified", r["updated_at"])
    due = r["due_at"].astimezone(MSK)
    e.add("dtstart", due - timedelta(minutes=30))
    e.add("dtend", due)
    e.add("summary", f"Дедлайн: {r['title']}")
    e.add("description", (r["details"] or "") + "\nКонцепт для конкурса, данные вымышлены.")
    e.add("categories", ["Дедлайн"])
    e.add("transp", "TRANSPARENT")
    a = Alarm()
    a.add("action", "DISPLAY")
    a.add("description", f"Завтра дедлайн: {r['title']}")
    a.add("trigger", timedelta(days=-1))
    e.add_component(a)
    return e


def make_calendar(name, events) -> bytes:
    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", name)
    cal.add("x-wr-timezone", config.TZ)
    cal.add("x-published-ttl", "PT1H")
    cal.add("refresh-interval", timedelta(hours=1), parameters={"VALUE": "DURATION"})
    for e in events:
        cal.add_component(e)
    cal.add_missing_timezones()
    return cal.to_ical()


def calendar_name(s):
    return f"Учёба · {s['last_name']} {s['first_name'][0]}."


def full_calendar(db, s) -> bytes:
    lessons, deadlines = calendar_rows(db, s)
    return make_calendar(calendar_name(s), [lesson_event(r) for r in lessons] + [deadline_event(r) for r in deadlines])


def ctag(db, s) -> str:
    """меняется при любом изменении занятий или дедлайнов студента — клиенты CalDAV по нему понимают, что пора обновиться"""
    lessons, deadlines = calendar_rows(db, s)
    h = hashlib.sha1()
    for r in lessons:
        h.update(f"{r['public_id']}:{r['sequence']}:{r['updated_at'].isoformat()};".encode())
    for r in deadlines:
        h.update(f"{r['public_id']}:{r['updated_at'].isoformat()};".encode())
    return h.hexdigest()[:24]


# ---------- ссылка-подписка ----------
def _feed_url(token):
    return f"{config.PUBLIC_URL}/cal/{token}.ics"


def subscription_links(url):
    webcal = "webcal://" + url.split("://", 1)[1]
    return {"https": url, "webcal": webcal,
            "google": "https://calendar.google.com/calendar/r?cid=" + quote(webcal, safe=""),
            "outlook": "https://outlook.live.com/calendar/0/addfromweb?url=" + quote(url, safe="") + "&name=" + quote("Учёба", safe=""),
            "yandex": "https://calendar.yandex.ru/"}


def qr_svg(text) -> str:
    import segno
    return segno.make(text, error="m").svg_data_uri(scale=4, border=2, dark="#14213d")


@router.get("/api/calendar")
def calendar_status(user=Depends(student_user), db=Depends(database)):
    feed = db.execute("SELECT * FROM calendar_feeds WHERE user_id=%s AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1", (user["id"],)).fetchone()
    pwds = db.execute("""SELECT public_id, label, created_at, last_used_at, last_client FROM app_passwords
        WHERE user_id=%s AND revoked_at IS NULL ORDER BY created_at DESC""", (user["id"],)).fetchall()
    host = config.PUBLIC_URL.split("://", 1)[1]
    return {"feed": {"created_at": feed["created_at"], "last_used_at": feed["last_used_at"], "hint": feed["token_hint"]} if feed else None,
            "caldav": {"server": f"{config.PUBLIC_URL}/dav/", "host": host, "login": user["login"],
                       "principal": f"{config.PUBLIC_URL}/dav/principals/{user['login']}/"},
            "app_passwords": [{"id": p["public_id"], "label": p["label"], "created_at": p["created_at"], "last_used_at": p["last_used_at"],
                               "client": p["last_client"]} for p in pwds]}


@router.post("/api/calendar/feed", dependencies=[Depends(mutation)])
def create_feed(user=Depends(student_user), db=Depends(database)):
    """новая ссылка; прежняя перестаёт работать. Сам токен показывается один раз — в базе только хэш"""
    token = new_token(24)
    with db.transaction():
        db.execute("UPDATE calendar_feeds SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (user["id"],))
        db.execute("INSERT INTO calendar_feeds (user_id, token_hash, token_hint) VALUES (%s, %s, %s)", (user["id"], token_hash(token), token[-4:]))
        audit(db, user["id"], "calendar.feed.create")
    url = _feed_url(token)
    links = subscription_links(url)
    return {"url": url, "links": links, "qr": qr_svg(links["webcal"])}


@router.delete("/api/calendar/feed", dependencies=[Depends(mutation)])
def revoke_feed(user=Depends(student_user), db=Depends(database)):
    with db.transaction():
        db.execute("UPDATE calendar_feeds SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (user["id"],))
        audit(db, user["id"], "calendar.feed.revoke")
    return {"ok": True}


class AppPasswordIn(Strict):
    label: str = Field(min_length=1, max_length=60)


@router.post("/api/calendar/app-passwords", dependencies=[Depends(mutation)])
def create_app_password(data: AppPasswordIn, user=Depends(sudo_user), db=Depends(database)):
    """пароль приложения для CalDAV: нужен свежий ввод основного пароля (окно 10 минут)"""
    if user["role"] != "student":
        raise ApiError(403, "Календарь доступен студентам")
    n = db.execute("SELECT count(*) AS n FROM app_passwords WHERE user_id=%s AND revoked_at IS NULL", (user["id"],)).fetchone()["n"]
    if n >= 10:
        raise ApiError(409, "Не больше 10 паролей приложений — удалите ненужные")
    pw = app_password()
    with db.transaction():
        db.execute("INSERT INTO app_passwords (public_id, user_id, label, secret_hash) VALUES (%s, %s, %s, %s)",
                   (public_id(), user["id"], data.label.strip(), token_hash(normalize_app_password(pw))))
        audit(db, user["id"], "calendar.app_password.create", data.label.strip())
    return {"password": pw, "login": user["login"], "server": f"{config.PUBLIC_URL}/dav/"}


@router.delete("/api/calendar/app-passwords/{pid}", dependencies=[Depends(mutation)])
def revoke_app_password(pid: str = Path(pattern=r"^[A-Za-z0-9_-]{8,32}$"), user=Depends(student_user), db=Depends(database)):
    n = db.execute("UPDATE app_passwords SET revoked_at=now() WHERE public_id=%s AND user_id=%s AND revoked_at IS NULL", (pid, user["id"])).rowcount
    if not n:
        raise ApiError(404, "Пароль приложения не найден")
    audit(db, user["id"], "calendar.app_password.revoke", pid)
    return {"ok": True}


def normalize_app_password(pw: str) -> str:
    """на телефоне пароль часто набирают без дефисов или с заглавными — принимаем и так"""
    return "".join(ch for ch in pw.lower() if ch.isalnum())


def ics_response(body: bytes, filename: str):
    return Response(body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "private, max-age=300"})


@router.get("/cal/{token}.ics")
def public_feed(request: Request, token: str = Path(pattern=r"^[A-Za-z0-9_-]{20,64}$"), db=Depends(database)):
    ratelimit.hit(db, f"feed:{rate_ip(request)}")
    feed = db.execute("""SELECT f.* FROM calendar_feeds f JOIN users u ON u.id = f.user_id
        WHERE f.token_hash=%s AND f.revoked_at IS NULL AND u.active""", (token_hash(token),)).fetchone()
    if not feed:
        raise ApiError(404, "Ссылка на календарь недействительна: её перевыпустили или отключили")
    if not feed["last_used_at"] or feed["last_used_at"] < clock.now() - timedelta(minutes=10):
        db.execute("UPDATE calendar_feeds SET last_used_at=now() WHERE id=%s", (feed["id"],))
    s = student(db, feed["user_id"])
    return ics_response(full_calendar(db, s), "ucheba.ics")


@router.get("/api/lessons/{pid}/event.ics")
def lesson_ics(pid: str = Path(pattern=r"^[A-Za-z0-9_-]{8,32}$"), user=Depends(student_user), db=Depends(database)):
    """одно занятие или экзамен файлом .ics — «Добавить в календарь» на любом телефоне"""
    s = student(db, user["id"])
    r = db.execute(LESSON_SQL + " WHERE l.public_id=%s AND l.group_ids && %s::int[]", (pid, s["group_ids"])).fetchone()
    if not r:
        raise ApiError(404, "Занятие не найдено")
    return Response(make_calendar(calendar_name(s), [lesson_event(r)]), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="event.ics"', "Cache-Control": "no-store"})


@router.get("/api/deadlines/{pid}/event.ics")
def deadline_ics(pid: str = Path(pattern=r"^[A-Za-z0-9_-]{8,32}$"), user=Depends(student_user), db=Depends(database)):
    s = student(db, user["id"])
    r = db.execute("""SELECT * FROM deadlines WHERE public_id=%s
        AND (student_id = %s OR (student_id IS NULL AND (group_ids && %s::int[] OR (group_ids IS NULL AND faculty_id = %s))))""",
                   (pid, s["user_id"], s["group_ids"], s["faculty_id"])).fetchone()
    if not r:
        raise ApiError(404, "Дедлайн не найден")
    return Response(make_calendar(calendar_name(s), [deadline_event(r)]), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="deadline.ics"', "Cache-Control": "no-store"})


def now_utc():
    return datetime.now(timezone.utc)
