"""Ограничение частоты: фиксированное окно в PostgreSQL (воркеры и копии приложения не делят память).
Атомарно: одно INSERT … ON CONFLICT DO UPDATE … RETURNING — параллельные запросы лимит не обходят."""
import random
import time

from .web import ApiError

LIMITS = {
    "login_ip": (30, 600),       # неудачных входов с одного адреса за 10 минут
    "login_user": (60, 600),     # неудачных входов в один логин со всех адресов
    "mfa": (10, 600),            # кодов 2FA с одного адреса (IPv6 — по сети /64)
    "mfa_user": (10, 600),       # кодов 2FA в один аккаунт со всех адресов
    "mfa_user_day": (30, 86400),
    "pwcheck": (40, 60),
    "reauth": (10, 600),
    "request_create": (20, 3600),
    "dav_fail": (20, 600),       # неверные пароли приложений с одного адреса
    "feed": (120, 3600),         # запросы ICS-ленты с одного адреса
}


def hit(db, key, limit=None, window=None, now=None, message="Слишком много запросов. Попробуйте чуть позже"):
    kind = key.split(":", 1)[0]
    if limit is None or window is None:
        limit, window = LIMITS[kind]
    now = now if now is not None else time.time()
    edge = now - window
    with db.transaction():
        row = db.execute("""INSERT INTO rate_limits (key, window_start, count) VALUES (%s, %s, 1)
            ON CONFLICT (key) DO UPDATE SET
              count = CASE WHEN rate_limits.window_start <= %s THEN 1 ELSE rate_limits.count + 1 END,
              window_start = CASE WHEN rate_limits.window_start <= %s THEN excluded.window_start ELSE rate_limits.window_start END
            RETURNING count, window_start""", (key, now, edge, edge)).fetchone()
        if random.random() < 0.01:  # nosec B311 — выборочная чистка старых окон
            db.execute("DELETE FROM rate_limits WHERE window_start < %s", (now - 2 * 86400,))
    if row["count"] > limit:
        retry = max(1, int(row["window_start"] + window - now) + 1)
        raise ApiError(429, message, code="rate_limited", headers={"Retry-After": str(retry)}, retry_after=retry)
    return row["count"]


def release(db, key):
    db.execute("UPDATE rate_limits SET count = greatest(0, count - 1) WHERE key = %s", (key,))
