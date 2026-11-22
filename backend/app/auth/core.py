"""Сеансы.

Учётная запись (логин + пароль [+ код 2FA])
├─ Устройство — ключ устройства: httpOnly-cookie на год, в базе только хэш. Доступа не даёт, нужен, чтобы узнать «то же устройство».
│  └─ Сеанс — живёт до выхода, отзыва или долгой неактивности (неделя … полгода, выбирает пользователь).
│     ├─ Ключ доступа — cookie, которая меняется каждые 30 минут. Старый ключ перестаёт действовать, как только новый впервые
│     │  пришёл с устройства (+2 минуты на параллельные запросы из других вкладок). Если старый ключ пришёл позже — это признак кражи
│     │  cookie: сеанс завершается, владелец получает уведомление.
│     │  Ответ с новым ключом потерялся (обрыв сети) — старый работает, пока новый ни разу не пришёл: ложных разлогинов нет.
│     └─ Окно подтверждения паролем (10 минут) для чувствительных действий: пароли приложений, смена пароля, 2FA.
└─ Ключ сеанса пришёл с чужой cookie устройства — сеанс не рвётся, но дальше работает только после ввода пароля.

Все функции с `with db.transaction()` фиксируют изменения сами."""
import json
from datetime import timedelta

from .. import config
from ..security import new_token, public_id, token_hash
from ..web import ApiError, client_ip
from . import clock, device

COOKIE = "lk_session"
DEVICE_COOKIE = "lk_device"
MFA_COOKIE = "lk_mfa"
DEVICE_DAYS = 365
ROTATE_AFTER = timedelta(minutes=30)
GRACE = timedelta(minutes=2)
SUDO = timedelta(minutes=10)
TOUCH_EVERY = timedelta(seconds=60)
TTL_OPTIONS = (7, 30, 90, 180)
TTL_DEFAULT = 30
KEEP_TOKENS = timedelta(days=30)
RETENTION = timedelta(days=183)          # история входов и завершённые сеансы хранятся 6 месяцев
REASONS = {
    "logout": "Вы вышли из кабинета",
    "terminated": "Сеанс завершён с другого вашего устройства",
    "token_reuse": "Сеанс завершён: его ключ доступа использовали повторно — похоже на кражу cookie. Войдите снова и смените пароль",
    "password_changed": "Пароль сменили — войдите с новым паролем",
    "inactivity": "Сеанс завершён из-за долгой неактивности",
    "user_blocked": "Доступ заблокирован",
    "expired": "Сеанс закончился — войдите снова",
}


def cookie_kw() -> dict:
    return dict(httponly=True, secure=config.COOKIE_SECURE, samesite="strict", path="/")


def queue_cookie(request, name, value, max_age=None):
    """cookie ставит middleware на любой ответ (JSON, файл, ошибка) — иначе новый ключ терялся бы на скачиваниях"""
    pending = getattr(request.state, "auth_cookies", None)
    if pending is None:
        pending = request.state.auth_cookies = []
    pending.append((name, value, max_age))


def apply_cookies(request, response):
    for name, value, max_age in getattr(request.state, "auth_cookies", None) or []:
        if value is None:
            response.delete_cookie(name, **cookie_kw())
        else:
            response.set_cookie(name, value, max_age=max_age, **cookie_kw())


def device_key(request):
    v = request.cookies.get(DEVICE_COOKIE) or ""
    return v if 20 <= len(v) <= 128 else None


def revoked_error(reason):
    return ApiError(401, REASONS.get(reason, "Сеанс завершён — войдите снова"), code="session_revoked", reason=reason)


# ---------- вход и история входов ----------
def login_event(db, user_id, login, result, request, reason=None, session_id=None, label=None):
    db.execute("""INSERT INTO login_events (user_id, login, ip, device_label, result, reason, session_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)""", (user_id, (login or "")[:120], client_ip(request)[:64],
                                                 (label or device.describe(request.headers)["label"])[:120], result, reason, session_id))


def start(db, user, request, *, mfa_passed=False) -> int:
    """новый сеанс после проверки пароля (и кода 2FA): устройство, сеанс, первый ключ; окно пароля открыто 10 минут"""
    now = clock.now()
    info = device.describe(request.headers)
    key = device_key(request) or new_token(24)
    kh = token_hash(key)
    ttl = user["session_ttl_days"] if user.get("session_ttl_days") in TTL_OPTIONS else TTL_DEFAULT
    token = new_token()
    with db.transaction():
        dev = db.execute("""INSERT INTO devices (user_id, key_hash, label, ua_family, os, model, first_seen_at, last_seen_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, key_hash) DO UPDATE SET label=excluded.label, ua_family=excluded.ua_family, os=excluded.os,
                model=excluded.model, last_seen_at=excluded.last_seen_at RETURNING id""",
                         (user["id"], kh, info["label"], info["browser"], info["os"], info["model"], now, now)).fetchone()
        sid = db.execute("""INSERT INTO sessions (public_id, user_id, device_id, created_at, last_active_at, last_ip, ua_json, mfa_passed,
                sudo_until, ttl_days) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                         (public_id(), user["id"], dev["id"], now, now, client_ip(request)[:64], json.dumps(info, ensure_ascii=False),
                          mfa_passed, now + SUDO, ttl)).fetchone()["id"]
        db.execute("INSERT INTO session_tokens (token_hash, session_id, issued_at) VALUES (%s, %s, %s)", (token_hash(token), sid, now))
        login_event(db, user["id"], user["login"], "ok", request, session_id=sid, label=info["label"])
        db.execute("UPDATE users SET last_login_at=%s WHERE id=%s", (now, user["id"]))
    queue_cookie(request, COOKIE, token, ttl * 86400)
    queue_cookie(request, DEVICE_COOKIE, key, DEVICE_DAYS * 86400)
    return sid


# ---------- каждый запрос ----------
_SELECT = """SELECT t.issued_at AS t_issued_at, t.first_seen_at AS t_first_seen_at, t.superseded_at AS t_superseded_at,
    s.*, u.login, u.role, u.active, u.demo, u.must_change_password, u.totp_enabled, d.key_hash AS device_key_hash
    FROM session_tokens t JOIN sessions s ON s.id = t.session_id JOIN users u ON u.id = s.user_id
    LEFT JOIN devices d ON d.id = s.device_id
    WHERE t.token_hash = %s"""
_ROTATE = "UPDATE session_tokens SET superseded_at=%s WHERE token_hash=%s AND superseded_at IS NULL"
_REISSUE = """UPDATE session_tokens SET superseded_at=%s WHERE session_id=%s AND superseded_at IS NULL AND first_seen_at IS NULL
    AND issued_at <= %s"""


def authenticate(db, request, *, allow_challenge=False) -> dict:
    """ключ доступа из cookie -> строка сеанса с полями пользователя; здесь же смена ключа, проверка устройства и неактивности"""
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 200:
        raise ApiError(401, "Нужен вход", code="login_required")
    th = token_hash(token)
    s = db.execute(_SELECT, (th,)).fetchone()
    if s is None:
        queue_cookie(request, COOKIE, None)
        raise revoked_error("expired")
    if s["revoked_at"]:
        queue_cookie(request, COOKIE, None)
        raise revoked_error(s["revoke_reason"])
    now = clock.now()
    if not s["active"]:
        revoke_user(db, s["user_id"], "user_blocked")
        raise revoked_error("user_blocked")
    if s["last_active_at"] + timedelta(days=s["ttl_days"]) < now:
        revoke(db, s["id"], "inactivity")
        raise revoked_error("inactivity")
    _token_state(db, request, s, th, now)
    _device_check(db, request, s, now)
    if s["challenge_at"] and not allow_challenge:
        raise ApiError(403, "Подтвердите вход паролем: этот сеанс открыли на другом устройстве", code="reauth_required", challenge=True)
    _touch(db, request, s, now)
    return s


def _token_state(db, request, s, th, now):
    if s["t_superseded_at"] is None:
        if s["t_first_seen_at"] is None:
            db.execute("UPDATE session_tokens SET first_seen_at=%s WHERE token_hash=%s AND first_seen_at IS NULL", (now, th))
        if s["t_issued_at"] + ROTATE_AFTER <= now:
            _issue(db, request, s, now, _ROTATE, (th,))
        return
    later_seen = db.execute("""SELECT MIN(first_seen_at) AS m FROM session_tokens WHERE session_id=%s AND issued_at > %s
        AND first_seen_at IS NOT NULL""", (s["id"], s["t_issued_at"])).fetchone()["m"]
    if later_seen:
        if later_seen + GRACE < now:
            compromise(db, s, "token_reuse")
            queue_cookie(request, COOKIE, None)
            raise revoked_error("token_reuse")
        return      # параллельный запрос из другой вкладки, ушедший до смены ключа
    if s["t_superseded_at"] + GRACE < now:
        _issue(db, request, s, now, _REISSUE, (s["id"], now - GRACE))


def _issue(db, request, s, now, sql, args):
    """новый ключ выпускает ровно один запрос: условный UPDATE в транзакции (строку блокирует PostgreSQL)"""
    token = new_token()
    with db.transaction():
        if db.execute(sql, (now, *args)).rowcount != 1:
            return False
        db.execute("INSERT INTO session_tokens (token_hash, session_id, issued_at) VALUES (%s, %s, %s)", (token_hash(token), s["id"], now))
    queue_cookie(request, COOKIE, token, s["ttl_days"] * 86400)
    return True


def _device_check(db, request, s, now):
    if s["challenge_at"] or not s["device_key_hash"]:
        return
    key = device_key(request)
    if key and token_hash(key) == s["device_key_hash"]:
        return
    info = device.describe(request.headers)
    with db.transaction():
        n = db.execute("UPDATE sessions SET challenge_at=%s, sudo_until=NULL WHERE id=%s AND challenge_at IS NULL", (now, s["id"])).rowcount
        if n:
            event(db, s["user_id"], "device_mismatch", s["id"], label=_label(s), seen_label=info["label"], ip=client_ip(request))
    s["challenge_at"] = now


def _touch(db, request, s, now):
    ip = client_ip(request)[:64]
    if ip == s["last_ip"] and s["last_active_at"] + TOUCH_EVERY > now:
        return
    with db.transaction():
        db.execute("UPDATE sessions SET last_active_at=%s, last_ip=%s WHERE id=%s", (now, ip, s["id"]))
        if s["device_id"]:
            db.execute("UPDATE devices SET last_seen_at=%s WHERE id=%s", (now, s["device_id"]))


# ---------- завершение ----------
def _revoke(db, sid, reason, by, now):
    n = db.execute("""UPDATE sessions SET revoked_at=%s, revoke_reason=%s, revoked_by_session_id=%s, sudo_until=NULL
        WHERE id=%s AND revoked_at IS NULL""", (now, reason, by, sid)).rowcount
    if n:
        db.execute("UPDATE session_tokens SET superseded_at=%s WHERE session_id=%s AND superseded_at IS NULL", (now, sid))
    return n


def revoke(db, sid, reason, by=None) -> int:
    with db.transaction():
        return _revoke(db, sid, reason, by, clock.now())


def revoke_user(db, user_id, reason, keep=None, by=None) -> int:
    """все сеансы пользователя, кроме keep (смена пароля, блокировка, «завершить все другие»)"""
    now = clock.now()
    with db.transaction():
        ids = [r["id"] for r in db.execute("SELECT id FROM sessions WHERE user_id=%s AND revoked_at IS NULL AND id IS DISTINCT FROM %s",
                                            (user_id, keep))]
        return sum(_revoke(db, sid, reason, by, now) for sid in ids)


def compromise(db, s, reason):
    """повтор старого ключа: сеанс завершается, владелец получает уведомление"""
    with db.transaction():
        _revoke(db, s["id"], reason, None, clock.now())
        event(db, s["user_id"], reason, s["id"], label=_label(s))
        notify_security(db, s["user_id"], EVENT_TEXT[reason].format(label=_label(s), seen_label="", place=""))


# ---------- уведомления о безопасности ----------
EVENT_TEXT = {
    "token_reuse": "Сеанс «{label}» завершён: его ключ доступа использовали повторно — похоже на кражу cookie. Если это были не вы, смените пароль.",
    "device_mismatch": "Сеанс «{label}» открыли с другого устройства ({seen_label}). Продолжить там можно только после ввода пароля.",
}


def event(db, user_id, kind, session_id=None, **details):
    db.execute("INSERT INTO security_events (user_id, kind, session_id, details) VALUES (%s, %s, %s, %s)",
               (user_id, kind, session_id, json.dumps(details, ensure_ascii=False)))


def notify_security(db, user_id, text):
    db.execute("""INSERT INTO notifications (public_id, user_id, kind, title, body, link, important)
        VALUES (%s, %s, 'security', 'Безопасность аккаунта', %s, '/security', true)""", (public_id(), user_id, text))


def _label(s) -> str:
    ua = s.get("ua_json") or {}
    if isinstance(ua, str):
        try:
            ua = json.loads(ua)
        except ValueError:
            ua = {}
    return ua.get("label") or "Неизвестное устройство"


# ---------- окно пароля ----------
def require_sudo(s):
    if not s.get("sudo_until") or s["sudo_until"] < clock.now():
        raise ApiError(403, "Подтвердите действие паролем", code="reauth_required")


def open_sudo(db, request, s):
    """пароль верный: окно 10 минут; если сеанс ждал подтверждения после смены устройства — привязываем его к этому устройству"""
    now = clock.now()
    new_key = None
    with db.transaction():
        if s["challenge_at"]:
            key = device_key(request)
            if not key:
                key = new_key = new_token(24)
            info = device.describe(request.headers)
            dev = db.execute("""INSERT INTO devices (user_id, key_hash, label, ua_family, os, model) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, key_hash) DO UPDATE SET last_seen_at=now() RETURNING id""",
                             (s["user_id"], token_hash(key), info["label"], info["browser"], info["os"], info["model"])).fetchone()
            db.execute("""UPDATE sessions SET sudo_until=%s, challenge_at=NULL, device_id=%s, ua_json=%s WHERE id=%s AND revoked_at IS NULL""",
                       (now + SUDO, dev["id"], json.dumps(info, ensure_ascii=False), s["id"]))
        else:
            db.execute("UPDATE sessions SET sudo_until=%s WHERE id=%s AND revoked_at IS NULL", (now + SUDO, s["id"]))
    if new_key:
        queue_cookie(request, DEVICE_COOKIE, new_key, DEVICE_DAYS * 86400)
    return now + SUDO


def set_ttl(db, user_id, days):
    with db.transaction():
        db.execute("UPDATE users SET session_ttl_days=%s WHERE id=%s", (days, user_id))
        db.execute("UPDATE sessions SET ttl_days=%s WHERE user_id=%s AND revoked_at IS NULL", (days, user_id))


# ---------- представления ----------
def session_view(r, current_id=None) -> dict:
    info = r["ua_json"] or {}
    return {"id": r["public_id"], "current": r["id"] == current_id, "label": info.get("label") or "Неизвестное устройство",
            "browser": info.get("browser") or "", "os": info.get("os") or "", "mobile": bool(info.get("mobile")),
            "ip": r["last_ip"], "created_at": r["created_at"], "last_active_at": r["last_active_at"], "challenge": bool(r["challenge_at"])}


def sessions_view(db, cur) -> dict:
    rows = db.execute("SELECT * FROM sessions WHERE user_id=%s AND revoked_at IS NULL ORDER BY last_active_at DESC, id DESC",
                      (cur["user_id"],)).fetchall()
    views = [session_view(r, cur["id"]) for r in rows]
    return {"current": next((v for v in views if v["current"]), None), "others": [v for v in views if not v["current"]],
            "ttl_days": cur["ttl_days"], "ttl_options": list(TTL_OPTIONS), "sudo_until": cur["sudo_until"]}


def login_history(db, user_id, days=30, limit=50) -> list:
    return [{"at": r["at"], "result": r["result"], "reason": r["reason"], "device": r["device_label"], "ip": r["ip"]}
            for r in db.execute("""SELECT at, result, reason, device_label, ip FROM login_events WHERE user_id=%s AND at > %s
                ORDER BY at DESC LIMIT %s""", (user_id, clock.now() - timedelta(days=days), limit))]


def find_session(db, user_id, pid):
    return db.execute("SELECT * FROM sessions WHERE user_id=%s AND public_id=%s AND revoked_at IS NULL", (user_id, pid)).fetchone()


# ---------- уборка ----------
def sweep(db):
    now = clock.now()
    expired = [r["id"] for r in db.execute("SELECT id, last_active_at, ttl_days FROM sessions WHERE revoked_at IS NULL")
               if r["last_active_at"] + timedelta(days=r["ttl_days"]) < now]
    for sid in expired:
        revoke(db, sid, "inactivity")
    edge = now - RETENTION
    with db.transaction():
        db.execute("DELETE FROM session_tokens WHERE superseded_at IS NOT NULL AND superseded_at < %s", (now - KEEP_TOKENS,))
        db.execute("DELETE FROM sessions WHERE revoked_at IS NOT NULL AND revoked_at < %s", (edge,))
        db.execute("DELETE FROM login_events WHERE at < %s", (edge,))
        db.execute("DELETE FROM security_events WHERE at < %s", (edge,))
        db.execute("DELETE FROM mfa_challenges WHERE created_at < %s", (now - timedelta(minutes=10),))
    return len(expired)
