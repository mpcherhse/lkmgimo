"""Настройки из переменных окружения. Секретов в коде нет: см. .env.example."""
import base64
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def env(name, default=None):
    return os.environ.get(name, default)


DSN = env("LK_DSN", "host=127.0.0.1 port=5460 dbname=lk user=lk")
PUBLIC_URL = env("LK_PUBLIC_URL", "http://127.0.0.1:8800").rstrip("/")
COOKIE_SECURE = env("LK_COOKIE_SECURE", "0") == "1"
TZ = "Europe/Moscow"
STATIC_DIR = Path(env("LK_STATIC_DIR", str(ROOT.parent / "frontend" / "dist")))
AUTO_SEED = env("LK_AUTO_SEED", "0") == "1"   # пустая база при старте заполняется демо-данными (хостинг без консоли)
DEMO_TOTP_HELPER = env("LK_DEMO_TOTP_HELPER", "0") == "1"   # страница с текущим кодом для демо-сотрудника (только стенд жюри)
FRESH_HOURS = float(env("LK_FRESH_HOURS", "0"))              # «новый вход» с ограничениями; 0 — выключено на демо-стенде
TODAY_OVERRIDE = env("LK_TODAY")                             # для тестов и скриншотов: зафиксировать «сегодня» (YYYY-MM-DD)


@lru_cache(maxsize=1)
def secret_key() -> bytes:
    """32 байта для AES-GCM (секреты TOTP). В бою — из менеджера секретов; в разработке — из .env"""
    raw = env("LK_SECRET_KEY")
    if not raw:
        raise RuntimeError("Не задан LK_SECRET_KEY (32 байта в base64). Сгенерировать: python -m app.cli secret-key")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("LK_SECRET_KEY должен быть 32 байта в base64")
    return key
