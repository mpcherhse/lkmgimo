"""Студент видит только свои данные: чужая заявка, уведомление, занятие, дедлайн, пароль приложения — 404,
даже если подставить точный идентификатор. Аноним — 401. Сотрудник — только свои факультеты."""
from conftest import H


def ids_of(c):
    reqs = [r["id"] for r in c.get("/api/requests").json()["items"]]
    notes = [n["id"] for n in c.get("/api/notifications").json()["items"]]
    days = c.get("/api/schedule?days=7").json()["days"]
    lessons = [l["id"] for d in days for l in d["lessons"]]
    deadlines = [d["id"] for d in c.get("/api/deadlines").json()["items"]]
    return reqs, notes, lessons, deadlines


def test_student_cannot_reach_other_students_data(anna, dan):
    a_reqs, a_notes, a_lessons, a_deadlines = ids_of(anna)
    d_lessons = set(ids_of(dan)[2])
    assert a_reqs and a_notes and a_lessons
    for rid in a_reqs:
        assert dan.get(f"/api/requests/{rid}").status_code == 404
        assert dan.post(f"/api/requests/{rid}/cancel", headers=H).status_code == 404
        assert dan.post(f"/api/requests/{rid}/messages", json={"text": "x"}, headers=H).status_code == 404
        assert dan.get(f"/api/requests/{rid}/document.pdf").status_code == 404
    for nid in a_notes:
        assert dan.post(f"/api/notifications/{nid}/read", headers=H).status_code == 404
    for lid in a_lessons:
        if lid not in d_lessons:
            assert dan.get(f"/api/lessons/{lid}/event.ics").status_code == 404
    private = [d for d in a_deadlines if d not in set(ids_of(dan)[3])]
    for did in private:
        assert dan.get(f"/api/deadlines/{did}/event.ics").status_code == 404


def test_lists_contain_only_own_records(anna, dan):
    a = set(ids_of(anna)[0])
    d = set(ids_of(dan)[0])
    assert a and d and not (a & d)
    assert anna.get("/api/profile").json()["last_name"] == "Соколова"
    assert dan.get("/api/profile").json()["last_name"] == "Белов"


def test_anonymous_gets_401(anon, anna):
    rid = ids_of(anna)[0][0]
    for path in ["/api/me", "/api/profile", "/api/dashboard", "/api/schedule", "/api/grades", f"/api/requests/{rid}", "/api/notifications",
                 "/api/calendar", "/api/staff/requests"]:
        assert anon.get(path).status_code == 401, path


def test_student_cannot_use_staff_api(anna, dan):
    rid = ids_of(anna)[0][0]
    assert anna.get("/api/staff/requests").status_code == 403
    assert dan.post(f"/api/staff/requests/{rid}/status", json={"status": "ready"}, headers=H).status_code == 403


def test_staff_sees_only_own_faculties(staff, masha):
    # сотрудник МО и МЭО не видит заявок студентки МП
    r = masha.post("/api/requests", json={"type": "question", "delivery": "electronic",
                                           "payload": {"topic": "Другое", "text": "Тестовый вопрос"}}, headers=H)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert staff.get(f"/api/staff/requests/{rid}").status_code == 404
    assert rid not in [x["id"] for x in staff.get("/api/staff/requests?status=all").json()["items"]]


def test_route_sweep_with_foreign_ids(app, anna, dan):
    """обход всех маршрутов с параметром: подставляем id чужих записей — ни один не отвечает 200"""
    a_reqs, a_notes, _, _ = ids_of(anna)
    foreign = a_reqs + a_notes
    hits = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/") or "{" not in path or "staff" in path or "verify" in path:
            continue
        for fid in foreign:
            url = path.replace("{pid}", fid).replace("{sid}", fid)
            for m in getattr(route, "methods", []) or []:
                if m == "GET":
                    r = dan.get(url)
                elif m == "POST":
                    r = dan.post(url, json={"text": "x"}, headers=H)
                elif m == "DELETE":
                    r = dan.delete(url, headers=H)
                else:
                    continue
                if r.status_code == 200:
                    hits.append((m, url))
    assert not hits, hits
