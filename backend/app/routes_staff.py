"""API сотрудника деканата: заявки своих факультетов, переносы занятий, объявления.
Вход сотрудника — только с кодом 2FA (приказ ФСТЭК № 117: многофакторная аутентификация для привилегированного доступа).
Сотрудник видит студентов и группы только своих факультетов; остальное — 404."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Path, Query
from pydantic import Field

from . import notify
from .auth.routes import Strict, staff_user
from .requests_logic import OPEN, STATUS_TEXT, status_label, add_event, make_certificate, next_statuses
from .routes_student import KIND_TEXT, LESSON_SQL, lesson_view
from .schedule_changes import change_text
from .timetable import MSK, PAIRS, pair_time, today
from .web import ApiError, audit, database, mutation

router = APIRouter()
PID = Path(pattern=r"^[A-Za-z0-9_-]{8,32}$")


def staff_scope(db, uid):
    row = db.execute("SELECT full_name, position FROM staff WHERE user_id=%s", (uid,)).fetchone()
    facs = db.execute("""SELECT f.* FROM staff_faculties sf JOIN faculties f ON f.id = sf.faculty_id WHERE sf.staff_id=%s ORDER BY f.code""",
                      (uid,)).fetchall()
    fids = [f["id"] for f in facs]
    groups = db.execute("SELECT * FROM groups WHERE faculty_id = ANY(%s) ORDER BY kind, code", (fids,)).fetchall()
    return {"name": row["full_name"], "position": row["position"], "faculties": facs, "faculty_ids": fids, "groups": groups,
            "group_ids": [g["id"] for g in groups]}


REQ_SQL = """SELECT r.*, t.title, t.category, t.electronic, t.days, t.fields, s.last_name, s.first_name, s.middle_name, s.course,
    g.code AS group_code, f.code AS faculty_code, s.faculty_id
    FROM requests r JOIN request_types t ON t.code = r.type_code JOIN students s ON s.user_id = r.student_id
    JOIN groups g ON g.id = s.group_id JOIN faculties f ON f.id = s.faculty_id"""


def _req_view(db, r, full=False):
    out = {"id": r["public_id"], "number": r["number"], "title": r["title"], "category": r["category"], "status": r["status"],
           "status_text": status_label(r["status"], r["category"]), "status_comment": r["status_comment"], "delivery": r["delivery"],
           "created_at": r["created_at"], "updated_at": r["updated_at"], "due_on": r["due_on"],
           "student": {"name": f"{r['last_name']} {r['first_name']} {r['middle_name']}".strip(), "group": r["group_code"],
                       "course": r["course"], "faculty": r["faculty_code"]},
           "next": sorted(next_statuses(r["status"], r["category"]), key=list(STATUS_TEXT).index), "overdue": bool(r["due_on"] and r["due_on"] < today() and r["status"] in OPEN and r["status"] != "ready")}
    if full:
        labels = {f["name"]: f["label"] for f in r["fields"]}
        out["payload"] = [{"label": labels.get(k, k), "value": v} for k, v in (r["payload"] or {}).items()]
        out["events"] = [{"at": e["at"], "status": e["status"], "status_text": status_label(e["status"], r["category"]) if e["status"] else None,
                          "message": e["message"], "author": e["author_role"], "author_name": e["author_name"]}
                         for e in db.execute("SELECT * FROM request_events WHERE request_id=%s ORDER BY at, id", (r["id"],))]
        cert = db.execute("SELECT number, verify_code FROM certificates WHERE request_id=%s", (r["id"],)).fetchone()
        out["document"] = {"number": cert["number"], "verify": f"/verify/{cert['verify_code']}"} if cert else None
    return out


def _scoped_request(db, scope, pid):
    r = db.execute(REQ_SQL + " WHERE r.public_id=%s AND s.faculty_id = ANY(%s)", (pid, scope["faculty_ids"])).fetchone()
    if not r:
        raise ApiError(404, "Заявка не найдена")
    return r


@router.get("/api/staff/overview")
def overview(user=Depends(staff_user), db=Depends(database)):
    sc = staff_scope(db, user["id"])
    counts = {r["status"]: r["n"] for r in db.execute("""SELECT r.status, count(*) AS n FROM requests r JOIN students s ON s.user_id = r.student_id
        WHERE s.faculty_id = ANY(%s) GROUP BY r.status""", (sc["faculty_ids"],))}
    overdue = db.execute("""SELECT count(*) AS n FROM requests r JOIN students s ON s.user_id = r.student_id
        WHERE s.faculty_id = ANY(%s) AND r.status = ANY(%s) AND r.due_on < %s""", (sc["faculty_ids"], list(OPEN - {"ready"}), today())).fetchone()["n"]
    students = db.execute("SELECT count(*) AS n FROM students WHERE faculty_id = ANY(%s)", (sc["faculty_ids"],)).fetchone()["n"]
    return {"name": sc["name"], "position": sc["position"], "faculties": [{"code": f["code"], "name": f["name"]} for f in sc["faculties"]],
            "counts": counts, "open": sum(v for k, v in counts.items() if k in OPEN), "overdue": overdue, "students": students}


@router.get("/api/staff/requests")
def staff_requests(status: str = Query(None, pattern=r"^(open|submitted|accepted|in_progress|ready|done|rejected|cancelled|all)$"),
                   q: str = Query(None, max_length=60), user=Depends(staff_user), db=Depends(database)):
    sc = staff_scope(db, user["id"])
    statuses = list(OPEN) if status in (None, "open") else (None if status == "all" else [status])
    like = f"%{q.strip()}%" if q and q.strip() else None
    rows = db.execute(REQ_SQL + """ WHERE s.faculty_id = ANY(%s) AND (%s::text[] IS NULL OR r.status = ANY(%s::text[]))
        AND (%s::text IS NULL OR s.last_name ILIKE %s OR r.number ILIKE %s OR t.title ILIKE %s)
        ORDER BY CASE r.status WHEN 'submitted' THEN 0 WHEN 'accepted' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'ready' THEN 3 ELSE 4 END,
                 r.created_at""", (sc["faculty_ids"], statuses, statuses, like, like, like, like)).fetchall()
    return {"items": [_req_view(db, r) for r in rows]}


@router.get("/api/staff/requests/{pid}")
def staff_request(pid: str = PID, user=Depends(staff_user), db=Depends(database)):
    sc = staff_scope(db, user["id"])
    return _req_view(db, _scoped_request(db, sc, pid), full=True)


class StatusIn(Strict):
    status: str = Field(pattern=r"^(accepted|in_progress|ready|done|rejected)$")
    comment: str = Field(default="", max_length=2000)


@router.post("/api/staff/requests/{pid}/status", dependencies=[Depends(mutation)])
def staff_set_status(data: StatusIn, pid: str = PID, user=Depends(staff_user), db=Depends(database)):
    sc = staff_scope(db, user["id"])
    r = _scoped_request(db, sc, pid)
    if data.status not in next_statuses(r["status"], r["category"]):
        raise ApiError(409, f"Из статуса «{STATUS_TEXT[r['status']]}» нельзя перейти в «{STATUS_TEXT[data.status]}»")
    if data.status == "rejected" and not data.comment.strip():
        raise ApiError(422, "Укажите причину отказа — студент увидит её в заявке")
    with db.transaction():
        n = db.execute("UPDATE requests SET status=%s, status_comment=%s, updated_at=now() WHERE id=%s AND status=%s",
                       (data.status, data.comment.strip(), r["id"], r["status"])).rowcount
        if not n:
            raise ApiError(409, "Заявку только что изменил другой сотрудник — обновите страницу")
        add_event(db, r["id"], data.status, data.comment.strip(), "staff", sc["name"])
        if data.status == "ready" and r["delivery"] == "electronic" and r["category"] == "certificate" and r["electronic"]:
            make_certificate(db, r["id"])
        text = data.comment.strip() or {"accepted": "Деканат принял заявку в работу", "in_progress": "Заявка в работе",
                                        "ready": ("Документ готов — скачайте его в заявке" if r["delivery"] == "electronic"
                                                  else "Документ готов — заберите в деканате с паспортом"),
                                        "done": "Заявка выполнена"}.get(data.status, "")
        notify.personal(db, r["student_id"], "request", f"{r['title']}: {status_label(data.status, r['category']).lower()}", text, f"/requests/{r['public_id']}",
                        important=data.status in ("ready", "rejected"))
        audit(db, user["id"], "staff.request.status", r["number"], status=data.status)
    return _req_view(db, _scoped_request(db, sc, pid), full=True)


class MessageIn(Strict):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/api/staff/requests/{pid}/messages", dependencies=[Depends(mutation)])
def staff_message(data: MessageIn, pid: str = PID, user=Depends(staff_user), db=Depends(database)):
    sc = staff_scope(db, user["id"])
    r = _scoped_request(db, sc, pid)
    with db.transaction():
        add_event(db, r["id"], None, data.text.strip(), "staff", sc["name"])
        db.execute("UPDATE requests SET updated_at=now() WHERE id=%s", (r["id"],))
        notify.personal(db, r["student_id"], "request", f"Ответ деканата: {r['title']}", data.text.strip()[:300], f"/requests/{r['public_id']}")
    return _req_view(db, _scoped_request(db, sc, pid), full=True)


# ---------- расписание ----------
@router.get("/api/staff/groups")
def staff_groups(user=Depends(staff_user), db=Depends(database)):
    sc = staff_scope(db, user["id"])
    return {"faculties": [{"id": f["id"], "code": f["code"], "name": f["name"]} for f in sc["faculties"]],
            "groups": [{"id": g["id"], "code": g["code"], "kind": g["kind"], "course": g["course"], "language": g["language"],
                        "faculty_id": g["faculty_id"]} for g in sc["groups"]]}


@router.get("/api/staff/lessons")
def staff_lessons(group: int = Query(...), start: date = Query(None, alias="from"), days: int = Query(7, ge=1, le=14),
                  user=Depends(staff_user), db=Depends(database)):
    sc = staff_scope(db, user["id"])
    if group not in sc["group_ids"]:
        raise ApiError(404, "Группа не найдена")
    start = start or today()
    st = datetime(start.year, start.month, start.day, tzinfo=MSK)
    rows = db.execute(LESSON_SQL + " WHERE %s = ANY(l.group_ids) AND l.starts_at >= %s AND l.starts_at < %s ORDER BY l.starts_at",
                      (group, st, st + timedelta(days=days))).fetchall()
    g = next(x for x in sc["groups"] if x["id"] == group)
    scheme = next(f["pair_scheme"] for f in sc["faculties"] if f["id"] == g["faculty_id"])
    return {"items": [lesson_view(r) for r in rows], "pairs": [{"n": i + 1, "start": a, "end": b} for i, (a, b) in enumerate(PAIRS[scheme])]}


class ChangeIn(Strict):
    cancel: bool = False
    day: date | None = None
    pair: int | None = Field(default=None, ge=1, le=8)
    room: str | None = Field(default=None, max_length=40)
    online: bool = False
    reason: str = Field(min_length=3, max_length=300)


@router.post("/api/staff/lessons/{pid}/change", dependencies=[Depends(mutation)])
def change_lesson(data: ChangeIn, pid: str = PID, user=Depends(staff_user), db=Depends(database)):
    """перенос, смена аудитории, перевод в онлайн или отмена: студенты получают уведомление, календари — новую версию события"""
    sc = staff_scope(db, user["id"])
    l = db.execute(LESSON_SQL + " WHERE l.public_id=%s AND l.group_ids && %s::int[]", (pid, sc["group_ids"])).fetchone()
    if not l:
        raise ApiError(404, "Занятие не найдено")
    if l["status"] == "cancelled":
        raise ApiError(409, "Занятие уже отменено")
    with db.transaction():
        if data.cancel:
            db.execute("""UPDATE lessons SET status='cancelled', change_reason=%s, changed_at=now(), sequence=sequence+1, updated_at=now()
                WHERE id=%s""", (data.reason.strip(), l["id"]))
        else:
            new_start, new_end = l["starts_at"], l["ends_at"]
            pair_no = l["pair_no"]
            if data.day or data.pair:
                g = db.execute("SELECT faculty_id FROM groups WHERE id=%s", (l["group_ids"][0],)).fetchone()
                scheme = db.execute("SELECT pair_scheme FROM faculties WHERE id=%s", (g["faculty_id"],)).fetchone()["pair_scheme"]
                day = data.day or l["starts_at"].astimezone(MSK).date()
                pair_no = data.pair or l["pair_no"] or 1
                new_start, new_end = pair_time(scheme, pair_no, day)
                if new_start.date() < today():
                    raise ApiError(422, "Нельзя перенести занятие в прошлое")
            room = l["room"] if data.room is None else data.room.strip()
            online_url = l["online_url"]
            building = l["building"]
            if data.online:
                room, building = "", ""
                online_url = online_url or "https://online.example.org/room/" + l["public_id"][:8]
            elif data.room:
                online_url = ""
                building = building or "пр. Вернадского, 76"
            if new_start == l["starts_at"] and room == l["room"] and online_url == l["online_url"]:
                raise ApiError(422, "Ничего не изменилось")
            db.execute("""UPDATE lessons SET status='moved', prev_starts_at=coalesce(prev_starts_at, starts_at), prev_ends_at=coalesce(prev_ends_at, ends_at),
                prev_room=coalesce(prev_room, room), starts_at=%s, ends_at=%s, pair_no=%s, room=%s, building=%s, online_url=%s, change_reason=%s,
                changed_at=now(), sequence=sequence+1, updated_at=now() WHERE id=%s""",
                       (new_start, new_end, pair_no, room, building, online_url, data.reason.strip(), l["id"]))
        fresh = db.execute(LESSON_SQL + " WHERE l.id=%s", (l["id"],)).fetchone()
        title, body = change_text(fresh, fresh["discipline"])
        users = [r["user_id"] for r in db.execute("""SELECT s.user_id FROM students s WHERE s.group_id = ANY(%s)
            OR EXISTS (SELECT 1 FROM student_language_groups x WHERE x.student_id = s.user_id AND x.group_id = ANY(%s))""",
                                                  (l["group_ids"], l["group_ids"]))]
        day = fresh["starts_at"].astimezone(MSK).date().isoformat()
        for uid in users:
            notify.personal(db, uid, "schedule", title, body, f"/schedule?date={day}", important=True)
        audit(db, user["id"], "staff.lesson.change", pid, cancel=data.cancel)
    return {"lesson": lesson_view(fresh), "notified": len(users)}


# ---------- объявления ----------
class AnnouncementIn(Strict):
    title: str = Field(min_length=3, max_length=140)
    body: str = Field(min_length=3, max_length=4000)
    important: bool = False
    faculty_id: int
    course: int | None = Field(default=None, ge=1, le=6)
    group_id: int | None = None


@router.post("/api/staff/announcements", dependencies=[Depends(mutation)])
def create_announcement(data: AnnouncementIn, user=Depends(staff_user), db=Depends(database)):
    sc = staff_scope(db, user["id"])
    if data.faculty_id not in sc["faculty_ids"]:
        raise ApiError(404, "Факультет не найден")
    if data.group_id is not None and data.group_id not in sc["group_ids"]:
        raise ApiError(404, "Группа не найдена")
    with db.transaction():
        pid, n = notify.publish(db, user["id"], data.title.strip(), data.body.strip(), data.important, data.faculty_id, data.course, data.group_id)
        audit(db, user["id"], "staff.announcement", pid, recipients=n)
    return {"id": pid, "recipients": n}


@router.get("/api/staff/announcements")
def list_announcements(user=Depends(staff_user), db=Depends(database)):
    sc = staff_scope(db, user["id"])
    rows = db.execute("""SELECT a.*, f.code AS faculty_code, g.code AS group_code,
        (SELECT count(*) FROM notifications n WHERE n.kind='announcement' AND n.title = a.title AND n.created_at >= a.published_at - interval '1 second') AS sent
        FROM announcements a LEFT JOIN faculties f ON f.id = a.faculty_id LEFT JOIN groups g ON g.id = a.group_id
        WHERE a.faculty_id = ANY(%s) ORDER BY a.published_at DESC LIMIT 30""", (sc["faculty_ids"],)).fetchall()
    return {"items": [{"id": r["public_id"], "title": r["title"], "body": r["body"], "important": r["important"], "faculty": r["faculty_code"],
                       "course": r["course"], "group": r["group_code"], "published_at": r["published_at"], "sent": r["sent"]} for r in rows]}


KIND = KIND_TEXT
