"""Тексты об изменениях в расписании — одни и те же для уведомлений, экрана расписания и календарей."""
from .timetable import MSK, WEEKDAYS, human_date


def _when(dt):
    d = dt.astimezone(MSK)
    return f"{WEEKDAYS[d.weekday()]}, {human_date(d.date())}, {d:%H:%M}"


def _sentence(text):
    text = (text or "").strip()
    return text if not text or text.endswith((".", "!", "?")) else text + "."


def change_text(lesson, discipline_name):
    """-> (заголовок, текст) для изменения занятия"""
    reason = _sentence(lesson.get("change_reason"))
    when = _when(lesson["starts_at"])
    when = when[:1].upper() + when[1:]
    if lesson["status"] == "cancelled":
        return f"Отмена: {discipline_name}", f"{when} — занятие отменено. {reason}".strip()
    parts = []
    moved = lesson.get("prev_starts_at") and lesson["prev_starts_at"] != lesson["starts_at"]
    if moved:
        parts.append(f"перенесено (было: {_when(lesson['prev_starts_at'])})")
    if lesson.get("prev_room") is not None and (lesson.get("prev_room") or "") != (lesson.get("room") or ""):
        new_room = f"ауд. {lesson['room']}" if lesson.get("room") else "онлайн"
        old_room = f"ауд. {lesson['prev_room']}" if lesson.get("prev_room") else "онлайн"
        parts.append(f"{old_room} → {new_room}")
    elif lesson.get("online_url") and not lesson.get("room"):
        parts.append("онлайн")
    what = "; ".join(parts) or "изменено"
    return f"Изменение: {discipline_name}", f"{when}: {what}. {reason}".strip()
