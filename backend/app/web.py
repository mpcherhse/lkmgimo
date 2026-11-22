"""Общее для маршрутов: ошибка с текстом для пользователя, соединение на запрос, защита от CSRF, журнал действий, адрес клиента."""
import ipaddress
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


_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _internal(ip) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip in _CGNAT


def client_ip(request: Request) -> str:
    """адрес клиента. X-Forwarded-For учитывается, только если запрос пришёл от внутреннего прокси (частный адрес),
    и берётся самый правый публичный адрес — его дописал наш прокси. Всё левее мог подставить сам клиент."""
    peer = (request.client.host if request.client else "") or "unknown"
    xff = request.headers.get("x-forwarded-for")
    if not xff:
        return peer
    try:
        if not _internal(ipaddress.ip_address(peer)):
            return peer
    except ValueError:
        return peer
    for part in reversed([p.strip() for p in xff.split(",")]):
        try:
            ip = ipaddress.ip_address(part)
        except ValueError:
            continue
        if not _internal(ip):
            return part
    return peer


def ip_bucket(ip: str) -> str:
    """ключ для лимитов частоты: IPv6 считается по сети /64 — одному абоненту обычно выдаётся вся сеть"""
    if ":" in ip:
        try:
            return str(ipaddress.ip_network(f"{ip}/64", strict=False).network_address) + "/64"
        except ValueError:
            return ip
    return ip


def rate_ip(request: Request) -> str:
    return ip_bucket(client_ip(request))
