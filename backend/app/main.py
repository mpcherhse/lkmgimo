"""Приложение «Цифровой деканат» (концепт для конкурса). Запуск: uvicorn app.main:app --proxy-headers --forwarded-allow-ips=<адрес прокси>"""
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import pyotp
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import caldav, calendar_feed, certificates, config, db as storage, routes_staff, routes_student
from .auth import core
from .auth import routes as auth_routes
from .auth.device import ACCEPT_CH
from .security import decrypt
from .web import ApiError

log = logging.getLogger("lk")


def _sweeper(stop):
    def loop():
        while not stop.wait(3600):
            try:
                with storage.connect() as db:
                    core.sweep(db)
            except Exception:  # noqa: BLE001 — уборка не должна ронять процесс
                log.exception("sweep failed")
    t = threading.Thread(target=loop, daemon=True, name="session-sweeper")
    t.start()


@asynccontextmanager
async def lifespan(app):
    with storage.direct() as conn:
        storage.migrate(conn)
    stop = threading.Event()
    _sweeper(stop)
    yield
    stop.set()
    storage.close_pool()


app = FastAPI(title="Цифровой деканат — API (концепт)", version="1.0", lifespan=lifespan,
              docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")

for r in (auth_routes.router, routes_student.router, routes_staff.router, calendar_feed.router, caldav.router, certificates.router):
    app.include_router(r)


@app.exception_handler(ApiError)
async def api_error(request: Request, exc: ApiError):
    body = {"detail": exc.detail}
    if exc.code:
        body["code"] = exc.code
    body.update(exc.extra)
    return JSONResponse(body, status_code=exc.status, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse({"detail": "Проверьте заполнение полей", "code": "validation",
                         "fields": [".".join(str(x) for x in e.get("loc", [])[1:]) for e in exc.errors()]}, status_code=422)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and not request.url.path.startswith(("/api/", "/dav/", "/cal/")):
        return _spa()
    text = {404: "Не найдено", 405: "Метод не поддерживается"}.get(exc.status_code, str(exc.detail))
    return JSONResponse({"detail": text}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "Что-то пошло не так на сервере. Попробуйте ещё раз через минуту", "code": "server_error"}, status_code=500)


CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; "
       "manifest-src 'self'; worker-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    core.apply_cookies(request, response)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if config.COOKIE_SECURE:
        h.setdefault("Strict-Transport-Security", "max-age=31536000")
    path = request.url.path
    if path.startswith("/api/"):
        h.setdefault("Cache-Control", "no-store")
    if h.get("content-type", "").startswith("text/html"):
        h.setdefault("Content-Security-Policy", CSP)
        h.setdefault("Accept-CH", ACCEPT_CH)
    return response


@app.get("/api/health")
def health():
    with storage.connect() as db:
        db.execute("SELECT 1")
    return {"ok": True}


@app.get("/api/demo/totp", include_in_schema=False)
def demo_totp():
    """ТОЛЬКО ДЛЯ СТЕНДА ЖЮРИ (LK_DEMO_TOTP_HELPER=1): текущий код 2FA общего демо-сотрудника, чтобы проверяющим не ставить
    приложение-аутентификатор. В действующей системе такого маршрута нет."""
    if not config.DEMO_TOTP_HELPER:
        raise ApiError(404, "Не найдено")
    with storage.connect() as db:
        row = db.execute("SELECT login, totp_secret_enc FROM users WHERE role='staff' AND demo AND totp_enabled ORDER BY id LIMIT 1").fetchone()
    if not row:
        raise ApiError(404, "Не найдено")
    totp = pyotp.TOTP(decrypt(row["totp_secret_enc"]))
    import time
    return {"login": row["login"], "code": totp.now(), "valid_for": 30 - int(time.time()) % 30}


@app.get("/api/demo/accounts", include_in_schema=False)
def demo_accounts():
    """ТОЛЬКО ДЛЯ СТЕНДА ЖЮРИ: подсказка с тестовыми аккаунтами на странице входа. Пароли берутся из окружения (LK_DEMO_PASSWORDS),
    в коде их нет; демо-аккаунтам запрещено менять пароль и 2FA. В действующей системе маршрута нет."""
    if not config.DEMO_TOTP_HELPER:
        raise ApiError(404, "Не найдено")
    import json
    import os
    try:
        passwords = json.loads(os.environ.get("LK_DEMO_PASSWORDS") or "{}")
    except ValueError:
        passwords = {}
    with storage.connect() as db:
        rows = db.execute("""SELECT u.login, u.role, s.last_name, s.first_name, s.course, f.code AS faculty, st.full_name, st.position
            FROM users u LEFT JOIN students s ON s.user_id = u.id LEFT JOIN faculties f ON f.id = s.faculty_id
            LEFT JOIN staff st ON st.user_id = u.id WHERE u.demo AND u.active ORDER BY u.role DESC, u.id""").fetchall()
    out = []
    for r in rows:
        if r["role"] == "student":
            who = f"Студент: {r['first_name']} {r['last_name']}, {r['faculty']}, {r['course']} курс"
        else:
            who = f"Сотрудник деканата: {r['full_name']} (вход с кодом 2FA)"
        out.append({"login": r["login"], "password": passwords.get(r["login"]), "who": who, "role": r["role"]})
    return {"items": out}


# ---------- фронтенд (сборка Vite) ----------
def _spa():
    index = config.STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return HTMLResponse("<!doctype html><meta charset=utf-8><title>Цифровой деканат</title><p>Фронтенд ещё не собран: cd frontend && npm run build</p>")


@app.get("/{path:path}", include_in_schema=False)
def static_or_spa(path: str):
    if path.startswith(("api/", "dav/", "cal/")):
        raise ApiError(404, "Не найдено")
    if path:
        f = (config.STATIC_DIR / path).resolve()
        base = config.STATIC_DIR.resolve()
        if f.is_file() and base in f.parents:
            cache = "public, max-age=31536000, immutable" if "/assets/" in f"/{path}" else "no-cache"
            return FileResponse(f, headers={"Cache-Control": cache})
    return _spa()
