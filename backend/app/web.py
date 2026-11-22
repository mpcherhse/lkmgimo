"""Общее для маршрутов: ошибка с текстом для пользователя, соединение на запрос, защита от CSRF, журнал действий, адрес клиента."""
import json
import logging
import re
from urllib.parse import urlparse

from fastapi import Request

from . import db as storage

audit_logger = logging.getLogger("lk.audit")
_CRLF = re.compile(r"[\r\n\x00  \x85]+")


class ApiError(Exception):
    """ответ {detail: текст по-русски, code: машинный код, ...}"""

    def __init__(self, status: int, detail: str, code: str = None, headers: dict = None, **extra):
        self.status, self.detail, self.code, self.headers, self.extra = status, detail, code, headers or {}, extra


def database():
    with storage.connect() as conn:
        yield conn


def same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and urlparse(origin).netloc != request.headers.get("host"):
        raise ApiError(403, "Недопустимый источник запроса")


def mutation(request: Request):
    """любой изменяющий запрос: тот же origin и собственный заголовок — форма с чужого сайта его не отправит"""
    same_origin(request)
    if request.headers.get("x-lk-request") != "1":
        raise ApiError(403, "Не хватает заголовка запроса")


def log_safe(value, limit=500) -> str:
    return _CRLF.sub(" ", str(value if value is not None else ""))[:limit]


def audit(db, user_id, action, target=None, **details):
    """журнал действий без паролей и секретов"""
    db.execute("INSERT INTO audit_log (user_id, action, target, details) VALUES (%s, %s, %s, %s)",
               (user_id, action, target, json.dumps(details, ensure_ascii=False) if details else None))
    audit_logger.info("%s %s %s", user_id, log_safe(action, 80), log_safe(target or "", 120))


def client_ip(request: Request) -> str:
    """адрес клиента. За обратным прокси uvicorn подставляет X-Forwarded-For только от доверенного прокси
    (--proxy-headers --forwarded-allow-ips); сами заголовки не читаем — их подделывает кто угодно"""
    return (request.client.host if request.client else "") or "unknown"
