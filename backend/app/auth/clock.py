"""Время в одном месте: тесты подменяют now()."""
from datetime import datetime, timezone

_offset = None


def now() -> datetime:
    t = datetime.now(timezone.utc)
    return t + _offset if _offset is not None else t


def shift(delta):
    """для тестов: сдвинуть часы"""
    global _offset
    _offset = delta
