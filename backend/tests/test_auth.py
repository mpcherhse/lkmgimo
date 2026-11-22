"""Вход, блокировка, CSRF, cookie, ротация ключа сеанса, 2FA сотрудника."""
from datetime import timedelta

import pyotp

from app.auth import clock
from conftest import H, PASSWORDS, TOTP, client


def test_wrong_password_generic_message(anon):
    r = anon.post("/api/login", json={"login": "a.sokolova", "password": "nope"}, headers=H)
    assert r.status_code == 401 and "Неверный логин или пароль" in r.json()["detail"]
    r2 = anon.post("/api/login", json={"login": "no.such.user", "password": "nope"}, headers=H)
    assert r2.status_code == 401 and r2.json()["detail"].startswith("Неверный логин или пароль")


def test_csrf_header_and_origin_required(anon):
    assert anon.post("/api/login", json={"login": "a.sokolova", "password": PASSWORDS["a.sokolova"]}).status_code == 403
    r = anon.post("/api/login", json={"login": "a.sokolova", "password": PASSWORDS["a.sokolova"]},
                  headers={**H, "origin": "https://evil.example"})
    assert r.status_code == 403


def test_unknown_body_fields_rejected(anon):
    r = anon.post("/api/login", json={"login": "a.sokolova", "password": "x", "role": "staff"}, headers=H)
    assert r.status_code == 422


def test_cookie_flags(app):
    c = client(app)
    with c:
        r = c.post("/api/login", json={"login": "m.kovaleva", "password": PASSWORDS["m.kovaleva"]}, headers=H)
        cookies = r.headers.get_list("set-cookie")
        sess = next(x for x in cookies if x.startswith("lk_session="))
        assert "HttpOnly" in sess and "SameSite=strict" in sess and "Path=/" in sess


def test_lockout_after_five_failures(app):
    from app.db import direct
    c = client(app)
    with c:
        for _ in range(5):
            assert c.post("/api/login", json={"login": "m.kovaleva", "password": "wrong"}, headers=H).status_code == 401
        r = c.post("/api/login", json={"login": "m.kovaleva", "password": PASSWORDS["m.kovaleva"]}, headers=H)
        assert r.status_code == 429
    with direct() as db:   # снять блокировку для остальных тестов
        db.execute("DELETE FROM login_attempts")
        db.execute("DELETE FROM rate_limits")


def test_passwords_are_hashed():
    from app.db import direct
    with direct() as db:
        for row in db.execute("SELECT login, password_hash FROM users"):
            assert row["password_hash"].startswith("$argon2id$")
            assert PASSWORDS[row["login"]] not in row["password_hash"]


def test_token_rotation_and_reuse_detection(app):
    c = client(app)
    with c:
        c.post("/api/login", json={"login": "a.sokolova", "password": PASSWORDS["a.sokolova"]}, headers=H)
        old = c.cookies.get("lk_session")
        try:
            clock.shift(timedelta(minutes=31))
            assert c.get("/api/me").status_code == 200
            new = c.cookies.get("lk_session")
            assert new and new != old
            assert c.get("/api/me").status_code == 200     # новый ключ «увиден»
            clock.shift(timedelta(minutes=35))
            thief = client(app)
            with thief:
                thief.cookies.set("lk_session", old)
                r = thief.get("/api/me")
                assert r.status_code == 401 and r.json()["code"] == "session_revoked"
            assert c.get("/api/me").status_code == 401       # сеанс завершён целиком
        finally:
            clock.shift(None)


def test_staff_requires_totp(app):
    c = client(app)
    with c:
        r = c.post("/api/login", json={"login": "dekanat", "password": PASSWORDS["dekanat"]}, headers=H)
        assert r.json() == {"ok": False, "mfa_required": True}
        assert c.get("/api/staff/overview").status_code == 401
        assert c.post("/api/login/mfa", json={"code": "000000"}, headers=H).status_code == 401
        clock.shift(timedelta(minutes=3))
        try:
            ok = c.post("/api/login/mfa", json={"code": pyotp.TOTP(TOTP).at(clock.now())}, headers=H)
            assert ok.status_code == 200
            assert c.get("/api/staff/overview").status_code == 200
            # тот же код второй раз не принимается
            c2 = client(app)
            with c2:
                c2.post("/api/login", json={"login": "dekanat", "password": PASSWORDS["dekanat"]}, headers=H)
                assert c2.post("/api/login/mfa", json={"code": pyotp.TOTP(TOTP).at(clock.now())}, headers=H).status_code == 401
        finally:
            clock.shift(None)


def test_demo_accounts_cannot_change_password(anna):
    r = anna.post("/api/me/password", json={"current": PASSWORDS["a.sokolova"], "new": "Совсем-Новый-Пароль-2026"}, headers=H)
    assert r.status_code == 403 and r.json()["code"] == "demo_locked"


def test_security_headers(anon):
    r = anon.get("/")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert anon.get("/api/me").headers["cache-control"] == "no-store"
