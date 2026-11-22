"""Календари: ICS-лента (подписка) и CalDAV только для чтения. CalDAV проверяется настоящим клиентом `caldav` по HTTP."""
import socket
import threading
import time
from datetime import timedelta

import pytest
from icalendar import Calendar

from conftest import H


def test_feed_lifecycle(anna, anon):
    r = anna.post("/api/calendar/feed", headers=H).json()
    path = "/" + r["url"].split("/", 3)[3]
    assert r["links"]["webcal"].startswith("webcal://") and "calendar.google.com" in r["links"]["google"]
    feed = anon.get(path)
    assert feed.status_code == 200 and feed.headers["content-type"].startswith("text/calendar")
    cal = Calendar.from_ical(feed.content)
    events = [c for c in cal.walk("VEVENT")]
    assert len(events) > 50
    assert cal.walk("VTIMEZONE"), "нужна зона Europe/Moscow"
    assert any(str(e.get("status")) == "CANCELLED" for e in events)
    # перевыпуск: старая ссылка умирает
    r2 = anna.post("/api/calendar/feed", headers=H).json()
    assert anon.get(path).status_code == 404
    assert anon.get("/" + r2["url"].split("/", 3)[3]).status_code == 200
    assert anon.get("/cal/" + "x" * 32 + ".ics").status_code == 404


def test_lesson_change_updates_feed(staff, anna, anon):
    feed = "/" + anna.post("/api/calendar/feed", headers=H).json()["url"].split("/", 3)[3]
    groups = staff.get("/api/staff/groups").json()["groups"]
    mo = next(g for g in groups if g["code"] == "МО-2-04")
    from app.timetable import today
    items = staff.get(f"/api/staff/lessons?group={mo['id']}&from={(today() + timedelta(days=1)).isoformat()}&days=7").json()["items"]
    lesson = next(x for x in items if x["status"] == "ok" and x["kind"] == "seminar")
    before = {str(e["uid"]): int(e.get("sequence", 0)) for e in Calendar.from_ical(anon.get(feed).content).walk("VEVENT")}
    r = staff.post(f"/api/staff/lessons/{lesson['id']}/change", json={"room": "А-512", "reason": "Ремонт аудитории"}, headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["notified"] >= 1
    uid = f"lesson-{lesson['id']}@lk-concept"
    after = {str(e["uid"]): e for e in Calendar.from_ical(anon.get(feed).content).walk("VEVENT")}
    assert int(after[uid]["sequence"]) == before[uid] + 1
    assert "А-512" in str(after[uid]["location"])
    assert any(n["kind"] == "schedule" and "Ремонт" in n["body"] for n in anna.get("/api/notifications?kind=schedule").json()["items"])
    ics = anna.get(f"/api/lessons/{lesson['id']}/event.ics")
    assert ics.status_code == 200 and b"BEGIN:VEVENT" in ics.content


def test_app_password_needs_fresh_password(app, anna):
    from conftest import PASSWORDS
    from app.auth import clock
    try:
        clock.shift(timedelta(minutes=15))
        r = anna.post("/api/calendar/app-passwords", json={"label": "Телефон"}, headers=H)
        assert r.status_code == 403 and r.json()["code"] == "reauth_required"
        assert anna.post("/api/me/reauth", json={"password": PASSWORDS["a.sokolova"]}, headers=H).status_code == 200
        r = anna.post("/api/calendar/app-passwords", json={"label": "Телефон"}, headers=H)
        assert r.status_code == 200 and len(r.json()["password"]) == 19
    finally:
        clock.shift(None)


@pytest.fixture(scope="module")
def live_server(app):
    import uvicorn
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(5)


def test_caldav_with_real_client(live_server, anna):
    import caldav
    pw = anna.post("/api/calendar/app-passwords", json={"label": "HarmonyOS"}, headers=H).json()["password"]
    client = caldav.DAVClient(url=live_server + "/.well-known/caldav", username="a.sokolova", password=pw)
    principal = client.principal()
    cals = principal.calendars()
    assert len(cals) == 1
    cal = cals[0]
    assert "Учёба" in cal.get_display_name()
    events = cal.events()
    assert len(events) > 50
    from app.timetable import now_msk
    now = now_msk()
    week = cal.search(start=now, end=now + timedelta(days=7), event=True, expand=False)
    assert 0 < len(week) < len(events)
    one = events[0]
    one.load()
    assert "BEGIN:VEVENT" in one.data
    # запись запрещена
    with pytest.raises(Exception):
        cal.save_event("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:x\nBEGIN:VEVENT\nUID:x\nDTSTART:20261201T100000Z\nDTEND:20261201T110000Z\n"
                       "SUMMARY:x\nEND:VEVENT\nEND:VCALENDAR")


def test_caldav_rejects_main_password_and_other_users(live_server, anna):
    import httpx
    from conftest import PASSWORDS
    r = httpx.request("PROPFIND", live_server + "/dav/", auth=("a.sokolova", PASSWORDS["a.sokolova"]), headers={"Depth": "0"})
    assert r.status_code == 401                      # основной пароль в CalDAV не принимается
    pw = anna.post("/api/calendar/app-passwords", json={"label": "Mac"}, headers=H).json()["password"]
    r = httpx.request("PROPFIND", live_server + "/dav/calendars/d.belov/study/", auth=("a.sokolova", pw), headers={"Depth": "1"})
    assert r.status_code == 404
    r = httpx.request("PROPFIND", live_server + "/dav/", auth=("d.belov", pw), headers={"Depth": "0"})
    assert r.status_code == 401                      # пароль приложения привязан к своему логину
    ok = httpx.request("PROPFIND", live_server + "/dav/calendars/a.sokolova/study/", auth=("a.sokolova", pw.replace("-", "").upper()),
                       headers={"Depth": "0"})
    assert ok.status_code == 207 and b"getctag" in ok.content
