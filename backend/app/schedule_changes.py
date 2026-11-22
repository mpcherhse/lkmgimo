"""Тексты об изменениях в расписании — одни и те же для уведомлений, экрана расписания и календарей."""
from .timetable import MSK, WEEKDAYS, human_date


def _when(dt):
    d = dt.astimezone(MSK)
    return f"{WEEKDAYS[d.weekday()]}, {human_date(d.date())}, {d:%H:%M}"


def change_text(lesson, discipline_name):
    """-> (заголовок, текст) для изменения занятия"""
    reason = lesson.get("change_reason") or ""
    if lesson["status"] == "cancelled":
        return f"Отмена: {discipline_name}", f"Занятие {_when(lesson['starts_at'])} отменено. {reason}".strip()
    parts = []
    if lesson.get("prev_starts_at") and lesson["prev_starts_at"] != lesson["starts_at"]:
        parts.append(f"перенесено с {_when(lesson['prev_starts_at'])} на {_when(lesson['starts_at'])}")
    if lesson.get("prev_room") is not None and (lesson.get("prev_room") or "") != (lesson.get("room") or ""):
        new_room = f"ауд. {lesson['room']}" if lesson.get("room") else "онлайн"
        old_room = f"ауд. {lesson['prev_room']}" if lesson.get("prev_room") else "онлайн"
        parts.append(f"{old_room} → {new_room}")
    what = "; ".join(parts) or "изменено"
    return f"Изменение: {discipline_name}", f"Занятие {_when(lesson['starts_at'])}: {what}. {reason}".strip()
