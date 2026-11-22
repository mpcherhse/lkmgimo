"""Уведомления: объявления деканата раскладываются по получателям при публикации (на масштабе вуза — очередь, см. docs/ARCHITECTURE.md)."""
from .security import public_id


def recipients(conn, faculty_id=None, course=None, group_id=None):
    return [r["user_id"] for r in conn.execute("""SELECT s.user_id FROM students s
        WHERE (%s::int IS NULL OR s.faculty_id = %s) AND (%s::int IS NULL OR s.course = %s)
          AND (%s::int IS NULL OR s.group_id = %s OR EXISTS (SELECT 1 FROM student_language_groups l WHERE l.student_id = s.user_id AND l.group_id = %s))""",
                                                (faculty_id, faculty_id, course, course, group_id, group_id, group_id))]


def publish(conn, author_id, title, body, important, faculty_id=None, course=None, group_id=None, at=None):
    pid = public_id()
    conn.execute("""INSERT INTO announcements (public_id, title, body, important, faculty_id, course, group_id, author_id, published_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()))""", (pid, title, body, important, faculty_id, course, group_id, author_id, at))
    users = recipients(conn, faculty_id, course, group_id)
    for uid in users:
        conn.execute("""INSERT INTO notifications (public_id, user_id, kind, title, body, link, important, created_at)
            VALUES (%s, %s, 'announcement', %s, %s, '', %s, coalesce(%s, now()))""", (public_id(), uid, title, body, important, at))
    return pid, len(users)


def personal(conn, user_id, kind, title, body="", link="", important=False):
    conn.execute("""INSERT INTO notifications (public_id, user_id, kind, title, body, link, important)
        VALUES (%s, %s, %s, %s, %s, %s, %s)""", (public_id(), user_id, kind, title, body, link, important))
