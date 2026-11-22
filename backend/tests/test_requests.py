"""Заявка проходит путь «подана → принята → в работе → готова → выдана»; статусы видит студент, справка проверяется по QR."""
import re
from conftest import H


def test_full_request_flow(anna, staff, anon):
    r = anna.post("/api/requests", json={"type": "study_cert", "delivery": "electronic",
                                          "payload": {"purpose": "В банк", "language": "Русский"}}, headers=H)
    assert r.status_code == 200, r.text
    req = r.json()
    assert req["status"] == "submitted" and re.fullmatch(r"\d{4}-\d{5}", req["number"])
    rid = req["id"]
    # недопустимый переход
    assert staff.post(f"/api/staff/requests/{rid}/status", json={"status": "done"}, headers=H).status_code == 409
    for st in ("accepted", "in_progress", "ready"):
        x = staff.post(f"/api/staff/requests/{rid}/status", json={"status": st, "comment": ""}, headers=H)
        assert x.status_code == 200, x.text
    mine = anna.get(f"/api/requests/{rid}").json()
    assert mine["status"] == "ready" and mine["document"]
    assert [e["status"] for e in mine["events"] if e["status"]] == ["submitted", "accepted", "in_progress", "ready"]
    pdf = anna.get(f"/api/requests/{rid}/document.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    notes = anna.get("/api/notifications?kind=request").json()["items"]
    assert any("готова" in n["title"] for n in notes)
    code = staff.get(f"/api/staff/requests/{rid}").json()["document"]["verify"].split("/")[-1]
    v = anon.get(f"/api/verify/{code}").json()
    assert v["valid"] and v["holder"].startswith("С") and "Соколова" not in v["holder"]
    assert anon.get("/api/verify/AAAAAAAAAAAAAAAA").status_code == 404
    # закрытую заявку отменить нельзя
    assert anna.post(f"/api/requests/{rid}/cancel", headers=H).status_code == 409


def test_cancel_only_submitted(dan):
    r = dan.post("/api/requests", json={"type": "question", "delivery": "electronic",
                                         "payload": {"topic": "Расписание", "text": "Когда пересдача?"}}, headers=H).json()
    assert r["can_cancel"]
    c = dan.post(f"/api/requests/{r['id']}/cancel", headers=H)
    assert c.status_code == 200 and c.json()["status"] == "cancelled"


def test_reject_needs_reason(dan, staff):
    r = dan.post("/api/requests", json={"type": "question", "delivery": "electronic",
                                         "payload": {"topic": "Другое", "text": "Вопрос"}}, headers=H).json()
    assert staff.post(f"/api/staff/requests/{r['id']}/status", json={"status": "rejected"}, headers=H).status_code == 422
    ok = staff.post(f"/api/staff/requests/{r['id']}/status", json={"status": "rejected", "comment": "Вопрос решён по почте"}, headers=H)
    assert ok.status_code == 200 and dan.get(f"/api/requests/{r['id']}").json()["status_comment"] == "Вопрос решён по почте"


def test_request_validation(anna):
    assert anna.post("/api/requests", json={"type": "nope", "delivery": "electronic", "payload": {}}, headers=H).status_code == 422
    bad = anna.post("/api/requests", json={"type": "study_cert", "delivery": "electronic", "payload": {}}, headers=H)
    assert bad.status_code == 422


def test_staff_message_reaches_student(anna, staff):
    rid = anna.get("/api/requests").json()["items"][0]["id"]
    staff.post(f"/api/staff/requests/{rid}/messages", json={"text": "Уточните, нужна ли печать"}, headers=H)
    ev = anna.get(f"/api/requests/{rid}").json()["events"]
    assert ev[-1]["message"] == "Уточните, нужна ли печать" and ev[-1]["author"] == "staff"


def test_announcement_scoping(staff, anna, dan, masha):
    groups = staff.get("/api/staff/groups").json()
    mo = next(f["id"] for f in groups["faculties"] if f["code"] == "МО")
    r = staff.post("/api/staff/announcements", json={"title": "Собрание курса МО", "body": "Во вторник в 18:00", "faculty_id": mo,
                                                     "important": True}, headers=H)
    assert r.status_code == 200 and r.json()["recipients"] >= 1
    assert any(n["title"] == "Собрание курса МО" for n in anna.get("/api/notifications").json()["items"])
    assert not any(n["title"] == "Собрание курса МО" for n in dan.get("/api/notifications").json()["items"])
    assert not any(n["title"] == "Собрание курса МО" for n in masha.get("/api/notifications").json()["items"])


def test_dashboard_and_grades(anna, dan, masha):
    d = anna.get("/api/dashboard").json()
    assert d["today"]["date"] and "deadlines" in d and d["rating"]["semester"]
    g = dan.get("/api/grades").json()
    assert g["weights"] == {"b1": 0.4, "b2": 0.5, "b3": 0.1}
    assert "discount" in g            # договорник видит условия скидки
    assert "discount" not in anna.get("/api/grades").json()
    assert masha.get("/api/grades").json()["history"] == []
