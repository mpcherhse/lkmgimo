"""Тесты гоняются на отдельной базе (LK_TEST_DSN). Перед сессией схема создаётся заново и заполняется демо-данными с известными паролями."""
import base64
import os

os.environ.setdefault("LK_SECRET_KEY", base64.b64encode(b"t" * 32).decode())
os.environ["LK_DSN"] = os.environ.get("LK_TEST_DSN", "host=127.0.0.1 port=5460 dbname=lk_test user=lk")
os.environ["LK_PUBLIC_URL"] = "http://testserver"

import pytest  # noqa: E402

PASSWORDS = {"a.sokolova": "Test-Anna-2026!", "d.belov": "Test-Dan-2026!", "m.kovaleva": "Test-Masha-2026!", "dekanat": "Test-Staff-2026!"}
TOTP = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
H = {"x-lk-request": "1"}


def reset_db():
    from app import seed
    from app.db import direct, migrate
    with direct() as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        migrate(c)
        seed.run(c, passwords=PASSWORDS, totp_secret=TOTP, verbose=False)


@pytest.fixture(scope="session", autouse=True)
def database():
    reset_db()
    yield


@pytest.fixture(scope="session")
def app():
    from app.main import app as application
    return application


def client(app):
    from fastapi.testclient import TestClient
    return TestClient(app, base_url="http://testserver")


@pytest.fixture
def anon(app):
    with client(app) as c:
        yield c


def login(app, who):
    c = client(app)
    c.__enter__()
    r = c.post("/api/login", json={"login": who, "password": PASSWORDS[who]}, headers=H)
    if who == "dekanat":
        assert r.json().get("mfa_required"), r.text
        import pyotp
        from app.db import direct
        # защита от повтора кода хранит последний принятый шаг TOTP; для фикстуры сбрасываем его
        with direct() as db:
            db.execute("UPDATE users SET totp_last_step=NULL WHERE login='dekanat'")
        r = c.post("/api/login/mfa", json={"code": pyotp.TOTP(TOTP).now()}, headers=H)
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def anna(app):
    c = login(app, "a.sokolova")
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def dan(app):
    c = login(app, "d.belov")
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def masha(app):
    c = login(app, "m.kovaleva")
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def staff(app):
    c = login(app, "dekanat")
    yield c
    c.__exit__(None, None, None)
