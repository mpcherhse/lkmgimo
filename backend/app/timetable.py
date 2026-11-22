"""Время пар, недели, «сегодня» по Москве. Время пар — с открытой страницы расписания МГИМО:
у МЭО, МП, МБ, ИМТУР обед после 2-й пары (схема A), у МО, ФУП, МЖ — после 3-й (схема B)."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import config

MSK = ZoneInfo(config.TZ)
PAIRS = {
    "A": [("09:00", "10:20"), ("10:35", "11:55"), ("12:55", "14:15"), ("14:30", "15:50"), ("16:00", "17:20"), ("17:30", "18:50"),
          ("19:00", "20:20"), ("20:30", "21:50")],
    "B": [("09:00", "10:20"), ("10:35", "11:55"), ("12:10", "13:30"), ("14:30", "15:50"), ("16:00", "17:20"), ("17:30", "18:50"),
          ("19:00", "20:20"), ("20:30", "21:50")],
}
WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def now_msk() -> datetime:
    from .auth import clock
    real = clock.now().astimezone(MSK)
    if config.TODAY_OVERRIDE:
        d = date.fromisoformat(config.TODAY_OVERRIDE)
        return real.replace(year=d.year, month=d.month, day=d.day)
    return real


def today() -> date:
    return now_msk().date()


def pair_time(scheme, n, day: date):
    start, end = PAIRS[scheme][n - 1]
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    return (datetime.combine(day, time(h1, m1), MSK), datetime.combine(day, time(h2, m2), MSK))


def week_no(day: date, semester_start: date) -> int:
    """1-я учебная (нечётная) неделя — та, на которую приходится начало семестра; недели с понедельника"""
    monday0 = semester_start - timedelta(days=semester_start.weekday())
    return (day - monday0).days // 7 + 1


def human_date(d: date) -> str:
    return f"{d.day} {MONTHS_GEN[d.month - 1]}"
