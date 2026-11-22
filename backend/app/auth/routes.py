"""Вход, выход, сеансы, 2FA и смена пароля. Зависимости FastAPI: кто вошёл и с какой ролью.
Коды ошибок для фронта: login_required/session_revoked (401), reauth_required (403), mfa_required, rate_limited (429)."""
from datetime import timedelta

import pyotp
from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field

from .. import ratelimit
from ..security import DUMMY_HASH, check_password, decrypt, encrypt, hash_password, new_token, token_hash, verify_password
from ..web import ApiError, audit, client_ip, database, mutation
from . import clock, core

router = APIRouter()
SID = Path(pattern=r"^[A-Za-z0-9_-]{8,32}$")
LOCK_AFTER = 5
LOCK_FOR = timedelta(minutes=15)
ISSUER = "Цифровой деканат (концепт)"


class Strict(BaseModel):
    """лишние поля в теле — 422: опечатка или попытка протащить чужое поле не проходит молча"""
    model_config = ConfigDict(extra="forbid")


# ---------- зависимости ----------
def _user(s):
    return {"id": s["user_id"], "login": s["login"], "role": s["role"], "demo": s["demo"], "totp_enabled": s["totp_enabled"],
            "must_change_password": s["must_change_password"], "session": s}


def session_user(request: Request, db=Depends(database)):
    return _user(core.authenticate(db, request))


def challenged_user(request: Request, db=Depends(database)):
    return _user(core.authenticate(db, request, allow_challenge=True))


def current_user(user=Depends(session_user)):
    if user["must_change_password"]:
        raise ApiError(403, "Сначала смените временный пароль", code="password_change_required")
    return user


def student_user(user=Depends(current_user)):
    if user["role"] != "student":
        raise ApiError(403, "Раздел доступен только студентам")
    return user


def staff_user(user=Depends(current_user)):
    if user["role"] != "staff":
        raise ApiError(403, "Раздел доступен только сотрудникам деканата")
    if not user["session"]["mfa_passed"]:
        raise ApiError(403, "Для сотрудников нужен вход с кодом 2FA", code="mfa_required")
    return user


def sudo_user(user=Depends(current_user)):
    core.require_sudo(user["session"])
    return user


# ---------- вход ----------
class LoginIn(Strict):
    login: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=1024)


class CodeIn(Strict):
    code: str = Field(min_length=6, max_length=8, pattern=r"^\d{6,8}$")


def normalize_login(value: str) -> str:
    return value.strip().lower()


def _reserve_attempt(db, key, now):
    """попытка засчитывается ДО проверки пароля и атомарно: параллельные запросы блокировку не обходят"""
    with db.transaction():
        db.execute("DELETE FROM login_attempts WHERE key=%s AND lock_until IS NOT NULL AND lock_until <= %s", (key, now))
        row = db.execute("""INSERT INTO login_attempts (key, failures) VALUES (%s, 1)
            ON CONFLICT (key) DO UPDATE SET failures = login_attempts.failures + 1 RETURNING failures, lock_until""", (key,)).fetchone()
    return row["failures"], row["lock_until"]


def _lock(db, key, now):
    db.execute("UPDATE login_attempts SET lock_until=%s WHERE key=%s AND lock_until IS NULL", (now + LOCK_FOR, key))


def _totp_ok(db, user, code) -> bool:
    """код TOTP с окном ±1 шаг; один и тот же код дважды не принимается"""
    if not user["totp_secret_enc"]:
        return False
    totp = pyotp.TOTP(decrypt(user["totp_secret_enc"]))
    now = clock.now().timestamp()
    for drift in (0, -1, 1):
        step = int(now // 30) + drift
        if pyotp.utils.strings_equal(totp.at(step * 30), code):
            n = db.execute("UPDATE users SET totp_last_step=%s WHERE id=%s AND (totp_last_step IS NULL OR totp_last_step < %s)",
                           (step, user["id"], step)).rowcount
            return n == 1
    return False


@router.post("/api/login", dependencies=[Depends(mutation)])
def login(data: LoginIn, request: Request, db=Depends(database)):
    login_name = normalize_login(data.login)
    now = clock.now()
    ip = client_ip(request)
    ip_key = f"login_ip:{ip}"
    ratelimit.hit(db, ip_key, message="Слишком много попыток входа с этого адреса. Попробуйте через 10 минут")
    ratelimit.hit(db, f"login_user:{login_name}", message="Слишком много попыток входа в этот аккаунт. Попробуйте позже")
    lock_key = f"{login_name}|{ip}"
    tries, lock_until = _reserve_attempt(db, lock_key, now)
    if (lock_until and lock_until > now) or tries > LOCK_AFTER:
        if not lock_until:
            _lock(db, lock_key, now)
        core.login_event(db, None, login_name, "fail", request, reason="locked")
        raise ApiError(429, "Слишком много неудачных попыток. Попробуйте через 15 минут", code="locked")
    user = db.execute("SELECT * FROM users WHERE login=%s", (login_name,)).fetchone()
    valid = verify_password(user["password_hash"] if user else DUMMY_HASH, data.password)
    if not user or not user["active"] or not valid:
        if tries >= LOCK_AFTER:
            _lock(db, lock_key, now)
        core.login_event(db, user["id"] if user else None, login_name, "fail", request,
                         reason="blocked" if user and valid else "password")
        left = max(0, LOCK_AFTER - tries)
        raise ApiError(401, "Неверный логин или пароль" + (f". Осталось попыток: {left}" if 0 < left <= 2 else ""), code="bad_credentials")
    ratelimit.release(db, ip_key)
    ratelimit.release(db, f"login_user:{login_name}")
    db.execute("DELETE FROM login_attempts WHERE key=%s", (lock_key,))
    if user["totp_enabled"] or user["role"] == "staff":
        if not user["totp_enabled"]:
            raise ApiError(403, "Для сотрудника не настроен второй фактор — обратитесь к администратору", code="mfa_not_configured")
        token = new_token()
        db.execute("INSERT INTO mfa_challenges (token_hash, user_id) VALUES (%s, %s)", (token_hash(token), user["id"]))
        core.queue_cookie(request, core.MFA_COOKIE, token, 300)
        return {"ok": False, "mfa_required": True}
    core.start(db, user, request)
    return {"ok": True}


@router.post("/api/login/mfa", dependencies=[Depends(mutation)])
def login_mfa(data: CodeIn, request: Request, db=Depends(database)):
    token = request.cookies.get(core.MFA_COOKIE) or ""
    ratelimit.hit(db, f"mfa:{client_ip(request)}", message="Слишком много попыток ввода кода. Попробуйте через 10 минут")
    ch = db.execute("SELECT * FROM mfa_challenges WHERE token_hash=%s", (token_hash(token),)).fetchone() if token else None
    if not ch or ch["created_at"] + timedelta(minutes=5) < clock.now() or ch["attempts"] >= 5:
        core.queue_cookie(request, core.MFA_COOKIE, None)
        raise ApiError(401, "Время на ввод кода истекло — войдите снова", code="mfa_expired")
    user = db.execute("SELECT * FROM users WHERE id=%s", (ch["user_id"],)).fetchone()
    if not _totp_ok(db, user, data.code):
        db.execute("UPDATE mfa_challenges SET attempts = attempts + 1 WHERE token_hash=%s", (ch["token_hash"],))
        core.login_event(db, user["id"], user["login"], "fail", request, reason="mfa")
        raise ApiError(401, "Неверный код. Возьмите свежий код в приложении-аутентификаторе", code="bad_code")
    db.execute("DELETE FROM mfa_challenges WHERE token_hash=%s", (ch["token_hash"],))
    core.queue_cookie(request, core.MFA_COOKIE, None)
    core.start(db, user, request, mfa_passed=True)
    return {"ok": True}


@router.post("/api/logout", dependencies=[Depends(mutation)])
def logout(request: Request, db=Depends(database)):
    try:
        s = core.authenticate(db, request, allow_challenge=True)
    except ApiError:
        s = None
    if s:
        core.revoke(db, s["id"], "logout", by=s["id"])
    core.queue_cookie(request, core.COOKIE, None)
    return {"ok": True}


class PasswordIn(Strict):
    password: str = Field(min_length=1, max_length=1024)


@router.post("/api/me/reauth", dependencies=[Depends(mutation)])
def reauth(data: PasswordIn, request: Request, user=Depends(challenged_user), db=Depends(database)):
    ratelimit.hit(db, f"reauth:{user['id']}", message="Слишком много попыток. Попробуйте через 10 минут")
    row = db.execute("SELECT password_hash FROM users WHERE id=%s", (user["id"],)).fetchone()
    if not verify_password(row["password_hash"], data.password):
        raise ApiError(401, "Неверный пароль", code="bad_password")
    until = core.open_sudo(db, request, user["session"])
    return {"ok": True, "sudo_until": until}


# ---------- сеансы и история ----------
@router.get("/api/me/sessions")
def my_sessions(user=Depends(current_user), db=Depends(database)):
    return core.sessions_view(db, user["session"])


@router.delete("/api/me/sessions/{sid}", dependencies=[Depends(mutation)])
def terminate_session(sid: str = SID, user=Depends(current_user), db=Depends(database)):
    s = user["session"]
    target = core.find_session(db, s["user_id"], sid)
    if not target:
        raise ApiError(404, "Сеанс не найден или уже завершён")
    if target["id"] == s["id"]:
        raise ApiError(400, "Чтобы завершить текущий сеанс, нажмите «Выйти»")
    core.revoke(db, target["id"], "terminated", by=s["id"])
    audit(db, user["id"], "session.terminate", sid)
    return {"ok": True}


@router.post("/api/me/sessions/terminate-others", dependencies=[Depends(mutation)])
def terminate_others(user=Depends(current_user), db=Depends(database)):
    n = core.revoke_user(db, user["id"], "terminated", keep=user["session"]["id"], by=user["session"]["id"])
    audit(db, user["id"], "session.terminate_others", None, count=n)
    return {"ok": True, "terminated": n}


@router.get("/api/me/logins")
def my_logins(user=Depends(current_user), db=Depends(database)):
    return {"items": core.login_history(db, user["id"])}


class TtlIn(Strict):
    days: int


@router.put("/api/me/session-ttl", dependencies=[Depends(mutation)])
def set_ttl(data: TtlIn, user=Depends(current_user), db=Depends(database)):
    if data.days not in core.TTL_OPTIONS:
        raise ApiError(422, "Недопустимый срок")
    core.set_ttl(db, user["id"], data.days)
    return {"ok": True}


# ---------- пароль ----------
class NewPasswordIn(Strict):
    current: str = Field(min_length=1, max_length=1024)
    new: str = Field(min_length=1, max_length=1024)


@router.post("/api/me/password/check", dependencies=[Depends(mutation)])
def password_check(data: PasswordIn, user=Depends(session_user), db=Depends(database)):
    ratelimit.hit(db, f"pwcheck:{user['id']}")
    return check_password(data.password, user["login"])


@router.post("/api/me/password", dependencies=[Depends(mutation)])
def change_password(data: NewPasswordIn, request: Request, user=Depends(session_user), db=Depends(database)):
    if user["demo"]:
        raise ApiError(403, "В общем тестовом аккаунте пароль не меняется, чтобы не помешать другим проверяющим", code="demo_locked")
    ratelimit.hit(db, f"reauth:{user['id']}", message="Слишком много попыток. Попробуйте через 10 минут")
    row = db.execute("SELECT password_hash FROM users WHERE id=%s", (user["id"],)).fetchone()
    if not verify_password(row["password_hash"], data.current):
        raise ApiError(401, "Текущий пароль указан неверно", code="bad_password")
    result = check_password(data.new, user["login"])
    if result["problems"]:
        raise ApiError(422, result["problems"][0], code="weak_password", problems=result["problems"])
    with db.transaction():
        db.execute("UPDATE users SET password_hash=%s, must_change_password=false WHERE id=%s", (hash_password(data.new), user["id"]))
        audit(db, user["id"], "password.change")
    core.revoke_user(db, user["id"], "password_changed", keep=user["session"]["id"])
    return {"ok": True}


# ---------- второй фактор (TOTP) ----------
@router.post("/api/me/2fa/setup", dependencies=[Depends(mutation)])
def totp_setup(user=Depends(sudo_user), db=Depends(database)):
    if user["demo"]:
        raise ApiError(403, "В общем тестовом аккаунте 2FA не меняется, чтобы не запереть других проверяющих", code="demo_locked")
    if user["totp_enabled"]:
        raise ApiError(409, "Второй фактор уже включён")
    secret = pyotp.random_base32()
    db.execute("UPDATE users SET totp_secret_enc=%s WHERE id=%s", (encrypt(secret), user["id"]))
    uri = pyotp.TOTP(secret).provisioning_uri(name=user["login"], issuer_name=ISSUER)
    import segno
    qr = segno.make(uri, error="m").svg_data_uri(scale=4, border=2)
    return {"secret": secret, "uri": uri, "qr": qr}


@router.post("/api/me/2fa/enable", dependencies=[Depends(mutation)])
def totp_enable(data: CodeIn, user=Depends(sudo_user), db=Depends(database)):
    row = db.execute("SELECT * FROM users WHERE id=%s", (user["id"],)).fetchone()
    if row["totp_enabled"] or not row["totp_secret_enc"]:
        raise ApiError(409, "Сначала начните настройку")
    if not _totp_ok(db, row, data.code):
        raise ApiError(422, "Код не подошёл. Проверьте время на телефоне и введите свежий код", code="bad_code")
    with db.transaction():
        db.execute("UPDATE users SET totp_enabled=true WHERE id=%s", (user["id"],))
        db.execute("UPDATE sessions SET mfa_passed=true WHERE id=%s", (user["session"]["id"],))
        audit(db, user["id"], "2fa.enable")
    return {"ok": True}


@router.post("/api/me/2fa/disable", dependencies=[Depends(mutation)])
def totp_disable(user=Depends(sudo_user), db=Depends(database)):
    if user["demo"] or user["role"] == "staff":
        raise ApiError(403, "Для этого аккаунта второй фактор обязателен", code="mfa_mandatory")
    with db.transaction():
        db.execute("UPDATE users SET totp_enabled=false, totp_secret_enc=NULL, totp_last_step=NULL WHERE id=%s", (user["id"],))
        audit(db, user["id"], "2fa.disable")
    return {"ok": True}
