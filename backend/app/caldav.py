"""CalDAV только для чтения (RFC 4791 + RFC 6578 sync-collection, минимальный набор, который нужен клиентам):
  /.well-known/caldav                     -> /dav/
  /dav/                                   PROPFIND: current-user-principal
  /dav/principals/<login>/                PROPFIND: calendar-home-set
  /dav/calendars/<login>/                 PROPFIND: домашняя коллекция, Depth 1 — календарь «study»
  /dav/calendars/<login>/study/           PROPFIND (getctag, sync-token), REPORT (calendar-query, calendar-multiget, sync-collection)
  /dav/calendars/<login>/study/<uid>.ics  GET
Запись (PUT, DELETE, MKCALENDAR) запрещена: расписание меняет только деканат. Вход — Basic: логин + пароль приложения."""
import base64
import hashlib
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse, Response

from . import db as storage, ratelimit
from .calendar_feed import (calendar_name, calendar_rows, ctag, deadline_event, deadline_uid, lesson_event, lesson_uid, make_calendar,
                            normalize_app_password)
from .routes_student import student
from .security import token_hash
from .web import ApiError, client_ip, rate_ip

router = APIRouter()
D, C, CS, A = "DAV:", "urn:ietf:params:xml:ns:caldav", "http://calendarserver.org/ns/", "http://apple.com/ns/ical/"
NS = {"d": D, "c": C, "cs": CS, "a": A}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
READ_METHODS = ["OPTIONS", "GET", "HEAD", "PROPFIND", "REPORT"]
WRITE_METHODS = ["PUT", "DELETE", "MKCALENDAR", "MKCOL", "PROPPATCH", "MOVE", "COPY", "POST", "LOCK", "UNLOCK"]
MAX_BODY = 256 * 1024
CAL = "study"


def q(ns, tag):
    return f"{{{ns}}}{tag}"


def _unauthorized():
    return Response("Нужен логин и пароль приложения из раздела «Календарь»", status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="lk-calendar", charset="UTF-8"', "Content-Type": "text/plain; charset=utf-8"})


def _auth(request: Request, db):
    """-> строка пользователя или None. Пароль — только пароль приложения (не основной пароль кабинета)"""
    h = request.headers.get("authorization") or ""
    if not h.lower().startswith("basic "):
        return None
    try:
        login, _, pw = base64.b64decode(h[6:].strip()).decode("utf-8").partition(":")
    except Exception:  # noqa: BLE001
        return None
    login = login.strip().lower()
    row = db.execute("""SELECT u.id, u.login, a.id AS app_id FROM app_passwords a JOIN users u ON u.id = a.user_id
        WHERE a.secret_hash=%s AND a.revoked_at IS NULL AND u.active AND u.role='student'""", (token_hash(normalize_app_password(pw)),)).fetchone()
    if not row or row["login"] != login:
        ratelimit.hit(db, f"dav_fail:{rate_ip(request)}", message="Слишком много неверных паролей")
        return None
    ua = (request.headers.get("user-agent") or "")[:120]
    db.execute("UPDATE app_passwords SET last_used_at=now(), last_client=%s WHERE id=%s AND (last_used_at IS NULL OR last_used_at < now() - interval '5 minutes')",
               (ua, row["app_id"]))
    return row


def _multistatus(responses) -> Response:
    root = ET.Element(q(D, "multistatus"))
    for href, found, missing in responses:
        r = ET.SubElement(root, q(D, "response"))
        ET.SubElement(r, q(D, "href")).text = href
        for status, props in (("HTTP/1.1 200 OK", found), ("HTTP/1.1 404 Not Found", missing)):
            if not props:
                continue
            ps = ET.SubElement(r, q(D, "propstat"))
            prop = ET.SubElement(ps, q(D, "prop"))
            for el in props:
                prop.append(el)
            ET.SubElement(ps, q(D, "status")).text = status
    body = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="utf-8")
    return Response(body, status_code=207, media_type="application/xml; charset=utf-8", headers={"DAV": "1, 3, calendar-access"})


def _el(tag, text=None, children=()):
    e = ET.Element(tag)
    if text is not None:
        e.text = text
    for c in children:
        e.append(c)
    return e


def _href(path):
    return _el(q(D, "href"), path)


async def _read_body(request: Request) -> bytes:
    """тело читается с ограничением ещё до разбора: заголовок Content-Length и фактический поток"""
    try:
        declared = int(request.headers.get("content-length") or 0)
    except ValueError:
        raise ApiError(400, "Неверный Content-Length") from None
    if declared > MAX_BODY:
        raise ApiError(413, "Слишком большой запрос")
    raw = bytearray()
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > MAX_BODY:
            raise ApiError(413, "Слишком большой запрос")
    return bytes(raw)


def _body(raw: bytes):
    if not raw.strip():
        return None
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        raise ApiError(400, "Неверный XML") from None


def _requested(root):
    """-> список запрошенных свойств (теги) или None, если allprop/пусто"""
    if root is None:
        return None
    prop = root.find(q(D, "prop"))
    if prop is None:
        return None
    return [child.tag for child in prop]


def _answer(requested, available: dict):
    if requested is None:
        return list(available.values()), []
    found, missing = [], []
    for tag in requested:
        if tag in available:
            found.append(available[tag])
        else:
            missing.append(ET.Element(tag))
    return found, missing


def _privileges():
    return _el(q(D, "current-user-privilege-set"), children=[_el(q(D, "privilege"), children=[_el(q(D, "read"))]),
                                                            _el(q(D, "privilege"), children=[_el(q(D, "read-current-user-privilege-set"))])])


def _principal_props(login, user_email=None):
    p = f"/dav/principals/{login}/"
    return {
        q(D, "current-user-principal"): _el(q(D, "current-user-principal"), children=[_href(p)]),
        q(D, "principal-URL"): _el(q(D, "principal-URL"), children=[_href(p)]),
        q(D, "resourcetype"): _el(q(D, "resourcetype"), children=[_el(q(D, "principal"))]),
        q(D, "displayname"): _el(q(D, "displayname"), login),
        q(C, "calendar-home-set"): _el(q(C, "calendar-home-set"), children=[_href(f"/dav/calendars/{login}/")]),
        q(C, "calendar-user-address-set"): _el(q(C, "calendar-user-address-set"), children=[_href(f"mailto:{login}@student.example.org")]),
        q(D, "supported-report-set"): _el(q(D, "supported-report-set")),
    }


def _home_props(login):
    return {
        q(D, "resourcetype"): _el(q(D, "resourcetype"), children=[_el(q(D, "collection"))]),
        q(D, "displayname"): _el(q(D, "displayname"), "Календари"),
        q(D, "current-user-principal"): _el(q(D, "current-user-principal"), children=[_href(f"/dav/principals/{login}/")]),
        q(D, "owner"): _el(q(D, "owner"), children=[_href(f"/dav/principals/{login}/")]),
        q(D, "current-user-privilege-set"): _privileges(),
    }


def _calendar_props(db, s, login):
    tag = ctag(db, s)
    sync = f"https://lk-concept/sync/{tag}"
    reports = _el(q(D, "supported-report-set"), children=[
        _el(q(D, "supported-report"), children=[_el(q(D, "report"), children=[_el(q(C, "calendar-query"))])]),
        _el(q(D, "supported-report"), children=[_el(q(D, "report"), children=[_el(q(C, "calendar-multiget"))])]),
        _el(q(D, "supported-report"), children=[_el(q(D, "report"), children=[_el(q(D, "sync-collection"))])])])
    return {
        q(D, "resourcetype"): _el(q(D, "resourcetype"), children=[_el(q(D, "collection")), _el(q(C, "calendar"))]),
        q(D, "displayname"): _el(q(D, "displayname"), calendar_name(s)),
        q(C, "calendar-description"): _el(q(C, "calendar-description"), "Расписание, сессия и дедлайны. Только чтение. Концепт, данные вымышлены."),
        q(C, "supported-calendar-component-set"): _el(q(C, "supported-calendar-component-set"), children=[ET.Element(q(C, "comp"), {"name": "VEVENT"})]),
        q(C, "calendar-timezone"): _el(q(C, "calendar-timezone"), make_calendar("tz", []).decode()),
        q(CS, "getctag"): _el(q(CS, "getctag"), tag),
        q(D, "sync-token"): _el(q(D, "sync-token"), sync),
        q(D, "getetag"): _el(q(D, "getetag"), f'"{tag}"'),
        q(A, "calendar-color"): _el(q(A, "calendar-color"), "#1F3A93FF"),
        q(A, "calendar-order"): _el(q(A, "calendar-order"), "1"),
        q(D, "current-user-privilege-set"): _privileges(),
        q(D, "owner"): _el(q(D, "owner"), children=[_href(f"/dav/principals/{login}/")]),
        q(D, "current-user-principal"): _el(q(D, "current-user-principal"), children=[_href(f"/dav/principals/{login}/")]),
        q(D, "supported-report-set"): reports,
        q(D, "getcontenttype"): _el(q(D, "getcontenttype"), "text/calendar; charset=utf-8"),
    }


def _objects(db, s):
    """-> {имя файла: (uid, etag, ics-bytes, last-modified)}"""
    lessons, deadlines = calendar_rows(db, s)
    name = calendar_name(s)
    out = {}
    for r in lessons:
        uid = lesson_uid(r)
        etag = hashlib.sha1(f"{uid}:{r['sequence']}:{r['updated_at'].isoformat()}".encode()).hexdigest()[:20]
        out[_filename(uid)] = (uid, etag, lambda r=r: make_calendar(name, [lesson_event(r)]), r["updated_at"], r["starts_at"], r["ends_at"])
    for r in deadlines:
        uid = deadline_uid(r)
        etag = hashlib.sha1(f"{uid}:{r['updated_at'].isoformat()}".encode()).hexdigest()[:20]
        out[_filename(uid)] = (uid, etag, lambda r=r: make_calendar(name, [deadline_event(r)]), r["updated_at"],
                               r["due_at"] - timedelta(minutes=30), r["due_at"])
    return out


def _filename(uid):
    return re.sub(r"[^A-Za-z0-9_-]", "_", uid.split("@")[0]) + ".ics"


def _object_props(item, with_data):
    uid, etag, data, modified, _s, _e = item
    props = {q(D, "getetag"): _el(q(D, "getetag"), f'"{etag}"'),
             q(D, "getcontenttype"): _el(q(D, "getcontenttype"), "text/calendar; charset=utf-8; component=VEVENT"),
             q(D, "resourcetype"): _el(q(D, "resourcetype")),
             q(D, "getlastmodified"): _el(q(D, "getlastmodified"), format_datetime(modified.astimezone(timezone.utc), usegmt=True))}
    if with_data:
        props[q(C, "calendar-data")] = _el(q(C, "calendar-data"), data().decode())
    return props


def _parse_utc(v):
    try:
        return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


@router.api_route("/.well-known/caldav", methods=READ_METHODS + WRITE_METHODS, include_in_schema=False)
async def well_known(request: Request):
    return RedirectResponse("/dav/", status_code=301)


@router.api_route("/dav/{path:path}", methods=READ_METHODS + WRITE_METHODS, include_in_schema=False)
async def dav(request: Request, path: str = ""):
    method = request.method.upper()
    if method == "OPTIONS":
        return Response(status_code=200, headers={"DAV": "1, 3, calendar-access", "Allow": ", ".join(READ_METHODS)})
    raw = await _read_body(request) if method in ("PROPFIND", "REPORT") else b""
    # работа с базой синхронная — в пуле потоков, чтобы не блокировать цикл событий
    return await run_in_threadpool(_dav_sync, request, path, method, raw)


def _dav_sync(request: Request, path: str, method: str, raw: bytes):
    with storage.connect() as db:
        user = _auth(request, db)
        if not user:
            return _unauthorized()
        if method in WRITE_METHODS:
            return Response("Календарь только для чтения: расписание меняет деканат", status_code=403,
                            headers={"Content-Type": "text/plain; charset=utf-8"})
        login = user["login"]
        parts = [p for p in path.split("/") if p]
        depth = request.headers.get("depth", "1" if method == "REPORT" else "0")
        root = _body(raw) if method in ("PROPFIND", "REPORT") else None

        # корень и принципал
        if not parts or parts == ["principals"] or (parts[0] == "principals" and len(parts) == 2):
            if len(parts) == 2 and parts[1] != login:
                return Response(status_code=404)
            if method != "PROPFIND":
                return Response(status_code=405)
            href = "/dav/" if not parts else f"/dav/principals/{login}/"
            found, missing = _answer(_requested(root), _principal_props(login))
            return _multistatus([(href, found, missing)])

        if parts[0] != "calendars" or len(parts) < 2 or parts[1] != login:
            return Response(status_code=404)
        s = student(db, user["id"])

        if len(parts) == 2:     # домашняя коллекция
            if method != "PROPFIND":
                return Response(status_code=405)
            req = _requested(root)
            out = [(f"/dav/calendars/{login}/", *_answer(req, _home_props(login)))]
            if depth == "1":
                out.append((f"/dav/calendars/{login}/{CAL}/", *_answer(req, _calendar_props(db, s, login))))
            return _multistatus(out)

        if parts[2] != CAL:
            return Response(status_code=404)
        base = f"/dav/calendars/{login}/{CAL}/"

        if len(parts) == 3:     # сам календарь
            if method in ("GET", "HEAD"):
                from .calendar_feed import full_calendar
                body = full_calendar(db, s)
                return Response(b"" if method == "HEAD" else body, media_type="text/calendar; charset=utf-8")
            if method == "PROPFIND":
                req = _requested(root)
                out = [(base, *_answer(req, _calendar_props(db, s, login)))]
                if depth == "1":
                    for fname, item in _objects(db, s).items():
                        out.append((base + fname, *_answer(req, _object_props(item, False))))
                return _multistatus(out)
            if method == "REPORT":
                return _report(db, s, login, base, root)
            return Response(status_code=405)

        # одно событие
        fname = parts[3]
        item = _objects(db, s).get(fname)
        if not item:
            return Response(status_code=404)
        if method in ("GET", "HEAD"):
            body = item[2]()
            return Response(b"" if method == "HEAD" else body, media_type="text/calendar; charset=utf-8",
                            headers={"ETag": f'"{item[1]}"'})
        if method == "PROPFIND":
            found, missing = _answer(_requested(root), _object_props(item, False))
            return _multistatus([(base + fname, found, missing)])
        return Response(status_code=405)


def _report(db, s, login, base, root):
    if root is None:
        return Response(status_code=400)
    objects = _objects(db, s)
    req = _requested(root)
    with_data = req is None or q(C, "calendar-data") in req

    def answer(fname, item):
        return (base + fname, *_answer(req, _object_props(item, with_data)))

    if root.tag == q(C, "calendar-multiget"):
        out = []
        for h in root.findall(q(D, "href")):
            fname = (h.text or "").rstrip("/").split("/")[-1]
            item = objects.get(fname)
            out.append(answer(fname, item) if item else ((h.text or ""), [], [ET.Element(q(D, "getetag"))]))
        return _multistatus(out)
    if root.tag == q(C, "calendar-query"):
        start = end = None
        tr = root.find(f".//{q(C, 'time-range')}")
        if tr is not None:
            start, end = _parse_utc(tr.get("start")), _parse_utc(tr.get("end"))
        out = [answer(fname, item) for fname, item in objects.items()
               if (start is None or item[5] > start) and (end is None or item[4] < end)]
        return _multistatus(out)
    if root.tag == q(D, "sync-collection"):
        # без журнала изменений: всегда полный список и новый токен (клиент сам сверяет ETag)
        resp = _multistatus([answer(fname, item) for fname, item in objects.items()])
        tree = ET.fromstring(resp.body)
        ET.SubElement(tree, q(D, "sync-token")).text = f"https://lk-concept/sync/{ctag(db, s)}"
        body = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(tree, encoding="utf-8")
        return Response(body, status_code=207, media_type="application/xml; charset=utf-8")
    return Response(status_code=403)
