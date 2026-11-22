"""Демо-данные. ВСЁ ВЫМЫШЛЕНО: студенты, преподаватели, телефоны, почты (домен example.org), номера зачёток и справок.
Совпадения с реальными людьми случайны. Реалии вуза (факультеты, время пар, система рейтинга) — из открытых источников.

Пароли тестовых аккаунтов в коде не хранятся: берутся из LK_DEMO_PASSWORDS (JSON {"логин": "пароль"}) или генерируются
и печатаются один раз. Секрет 2FA демо-сотрудника — из LK_DEMO_TOTP_SECRET или генерируется."""
import json
import os
import random
import secrets
from datetime import date, datetime, timedelta

import pyotp

from . import db as storage
from .security import encrypt, hash_password, public_id
from .timetable import MSK, pair_time

FACULTIES = [
    ("МО", "Факультет международных отношений", "B", "Деканат МО: корпус 1, ауд. 1105 (вымышл.). Приём: пн–пт 10:00–17:00, обед 13:00–14:00",
     "+7 (000) 000-01-05", "dekanat-mo@example.org"),
    ("МЭО", "Факультет международных экономических отношений", "A", "Деканат МЭО: корпус 1, ауд. 2210 (вымышл.). Приём: пн–пт 10:00–17:00",
     "+7 (000) 000-02-10", "dekanat-meo@example.org"),
    ("МП", "Международно-правовой факультет", "A", "Деканат МП: корпус 2, ауд. 3014 (вымышл.). Приём: пн–чт 10:00–16:00",
     "+7 (000) 000-03-14", "dekanat-mp@example.org"),
]

ADDRESS = "пр. Вернадского, 76"

TEACHERS = {
    "zimina": ("Зимина О. В.", "проф."), "lebedev": ("Лебедев К. А.", "доц."), "grishin": ("Гришин П. Н.", "ст. преп."),
    "morozova": ("Морозова Е. Л.", "доц."), "tarasov": ("Тарасов И. М.", "ст. преп."), "ershova": ("Ершова Т. П.", "ст. преп."),
    "mironov": ("Миронов С. С.", "преп."), "kravets": ("Кравец А. Ю.", "доц."), "safronov": ("Сафронов Д. В.", "проф."),
    "lanskaya": ("Ланская В. А.", "доц."), "karpova": ("Карпова Л. Д.", "ст. преп."), "fomina": ("Фомина Р. К.", "ст. преп."),
    "polyakova": ("Полякова Ю. А.", "проф."), "vetrov": ("Ветров Г. Б.", "доц."), "sedova": ("Седова Е. М.", "преп."),
    "orlov": ("Орлов Д. Р.", "доц."),
}

# студенты: логин, ФИО, факультет, направление, профиль, курс, академическая группа, языковые группы, финансирование, год поступления
STUDENTS = [
    ("a.sokolova", ("Соколова", "Анна", "Дмитриевна"), "МО", "41.03.05 Международные отношения", "Мировая политика и дипломатия", 2,
     "МО-2-04", [("АНГЛ-2-07", "Английский"), ("НЕМ-2-03", "Немецкий")], "budget", 2025, "Зимина О. В."),
    ("d.belov", ("Белов", "Даниил", "Игоревич"), "МЭО", "38.03.01 Экономика", "Мировая экономика", 3,
     "МЭО-3-02", [("АНГЛ-3-11", "Английский"), ("ФР-3-05", "Французский")], "contract", 2024, "Кравец А. Ю."),
    ("m.kovaleva", ("Ковалёва", "Мария", "Сергеевна"), "МП", "40.03.01 Юриспруденция", "Международное право", 1,
     "МП-1-06", [("АНГЛ-1-14", "Английский"), ("ИСП-1-02", "Испанский")], "budget", 2026, ""),
]

STAFF = ("dekanat", "Орлова Светлана Викторовна", "Специалист по учебно-методической работе деканатов МО и МЭО", ["МО", "МЭО"])

# дисциплины текущего семестра: (название, преподаватель, контроль, [(день недели 0–6, пара, вид, аудитория, чётность: None|'odd'|'even', онлайн)])
CURRENT = {
    "МО-2-04": [
        ("Теория международных отношений", "zimina", "exam", [(0, 2, "lecture", "1205", None, False), (2, 3, "seminar", "3111", None, False)]),
        ("История международных отношений", "lebedev", "exam", [(1, 1, "lecture", "1205", None, False), (3, 2, "seminar", "2208", None, False)]),
        ("Мировая экономика", "grishin", "zachet", [(4, 2, "lecture", "1101", None, False), (4, 3, "seminar", "2115", "even", False)]),
        ("Политическая география", "morozova", "zachet", [(1, 3, "seminar", "3021", "odd", False)]),
        ("Физическая культура", "mironov", "zachet", [(3, 5, "seminar", "Спорткомплекс", None, False)]),
    ],
    "АНГЛ-2-07": [("Английский язык (основной)", "tarasov", "exam",
                   [(0, 4, "language", "2034", None, False), (2, 4, "language", "2034", None, False), (4, 4, "language", "2034", None, False)])],
    "НЕМ-2-03": [("Немецкий язык (второй)", "ershova", "zachet", [(1, 4, "language", "4120", None, False), (3, 4, "language", "4120", None, False)])],
    "МЭО-3-02": [
        ("Международные финансы", "kravets", "exam", [(0, 1, "lecture", "1101", None, False), (2, 2, "seminar", "2311", None, False)]),
        ("Эконометрика", "safronov", "exam", [(1, 2, "lecture", "1205", None, False), (3, 3, "seminar", "", None, True)]),
        ("Мировые товарные рынки", "lanskaya", "zachet", [(4, 1, "lecture", "1210", "odd", False), (4, 2, "seminar", "2302", None, False)]),
        ("Международный бизнес", "grishin", "zachet", [(1, 4, "seminar", "3104", None, False)]),
    ],
    "АНГЛ-3-11": [("Английский язык (основной)", "karpova", "exam",
                   [(0, 3, "language", "2040", None, False), (2, 3, "language", "2040", None, False), (3, 4, "language", "2040", None, False)])],
    "ФР-3-05": [("Французский язык (второй)", "fomina", "zachet", [(1, 5, "language", "4012", None, False), (4, 4, "language", "4012", None, False)])],
    "МП-1-06": [
        ("Теория государства и права", "polyakova", "exam", [(0, 1, "lecture", "1210", None, False), (2, 1, "seminar", "3008", None, False)]),
        ("Римское право", "vetrov", "exam", [(1, 2, "lecture", "1101", None, False), (3, 1, "seminar", "3010", None, False)]),
        ("Введение в международное право", "lanskaya", "zachet", [(4, 3, "lecture", "1205", None, False)]),
        ("История России", "orlov", "zachet", [(2, 4, "seminar", "2115", "odd", False)]),
    ],
    "АНГЛ-1-14": [("Английский язык (основной)", "karpova", "exam",
                   [(0, 3, "language", "2041", None, False), (3, 3, "language", "2041", None, False), (4, 2, "language", "2041", None, False)])],
    "ИСП-1-02": [("Испанский язык (второй)", "sedova", "zachet", [(1, 4, "language", "4033", None, False), (3, 4, "language", "4033", None, False)])],
}
# у лекций — поток из двух групп
STREAM = {"МО-2-04": ["МО-2-04", "МО-2-05"], "МЭО-3-02": ["МЭО-3-02", "МЭО-3-01"], "МП-1-06": ["МП-1-06", "МП-1-05"]}

# прошлые семестры: (код семестра, [(дисциплина, контроль, срезы, премия, экзамен, соц., пересдачи)], бонус)
HISTORY = {
    "a.sokolova": [
        ("2025-1", [("Введение в теорию международных отношений", "exam", (88, 92, 90), 0, 91, 95, 0),
                    ("История России", "zachet", (84, 86, 90), 2, None, 90, 0),
                    ("Английский язык (основной)", "exam", (93, 90, 95), 0, 94, 100, 0),
                    ("Немецкий язык (второй)", "zachet", (78, 82, 80), 0, None, 85, 0),
                    ("Основы экономической теории", "exam", (72, 80, 78), 0, 84, 85, 0)], 2),
        ("2025-2", [("История международных отношений (часть 1)", "exam", (90, 94, 92), 3, 93, 95, 0),
                    ("Политология", "exam", (85, 83, 88), 0, 87, 90, 0),
                    ("Английский язык (основной)", "exam", (95, 92, 94), 0, 96, 100, 0),
                    ("Немецкий язык (второй)", "zachet", (80, 84, 86), 0, None, 90, 0),
                    ("Философия", "zachet", (66, 70, 68), 0, 69, 80, 0)], 3),
    ],
    "d.belov": [
        ("2024-1", [("Микроэкономика", "exam", (80, 84, 82), 0, 85, 90, 0), ("Математический анализ", "exam", (70, 74, 78), 0, 80, 85, 0),
                    ("Английский язык (основной)", "exam", (88, 90, 86), 0, 90, 95, 0), ("История России", "zachet", (82, 86, 84), 0, None, 90, 0)], 0),
        ("2024-2", [("Макроэкономика", "exam", (84, 86, 88), 0, 88, 90, 0), ("Статистика", "exam", (58, 62, 60), 0, 72, 75, 1),
                    ("Английский язык (основной)", "exam", (90, 88, 92), 0, 91, 95, 0), ("Французский язык (второй)", "zachet", (76, 80, 82), 0, None, 85, 0)], 1),
        ("2025-1", [("Мировая экономика", "exam", (88, 90, 92), 2, 92, 95, 0), ("Финансы", "exam", (86, 84, 88), 0, 89, 90, 0),
                    ("Английский язык (основной)", "exam", (92, 90, 94), 0, 93, 95, 0), ("Французский язык (второй)", "zachet", (84, 86, 82), 0, None, 90, 0)], 2),
        ("2025-2", [("Международные валютно-кредитные отношения", "exam", (90, 92, 88), 0, 91, 95, 0),
                    ("Бухгалтерский учёт", "zachet", (74, 80, 78), 0, None, 85, 0),
                    ("Английский язык (основной)", "exam", (94, 92, 90), 0, 92, 95, 0), ("Французский язык (второй)", "zachet", (86, 88, 90), 0, None, 95, 0)], 2),
    ],
    "m.kovaleva": [],
}

# текущие оценки по срезам (срез 3 ещё впереди): логин -> {дисциплина: (срез1, срез2, премия)}
CURRENT_SLICES = {
    "a.sokolova": {"Теория международных отношений": (92, 88, 2), "История международных отношений": (86, 91, 0), "Мировая экономика": (74, 80, 0),
                   "Политическая география": (90, 94, 0), "Физическая культура": (85, 90, 0), "Английский язык (основной)": (95, 93, 0),
                   "Немецкий язык (второй)": (66, 71, 0)},
    "d.belov": {"Международные финансы": (84, 88, 0), "Эконометрика": (62, 70, 0), "Мировые товарные рынки": (80, 78, 0),
                "Международный бизнес": (91, 89, 3), "Английский язык (основной)": (90, 92, 0), "Французский язык (второй)": (78, 74, 0)},
    "m.kovaleva": {"Теория государства и права": (78, 84, 0), "Римское право": (70, None, 0), "Введение в международное право": (88, 90, 0),
                   "История России": (92, 86, 0), "Английский язык (основной)": (85, 89, 0), "Испанский язык (второй)": (60, 66, 0)},
}

REQUEST_TYPES = [
    ("study_cert", "Справка об обучении", "certificate", "Подтверждает, что вы учитесь в университете. Подходит для работы, банка, визы, налогового вычета.", 1,
     [{"name": "purpose", "label": "Куда нужна справка", "type": "select", "required": True,
       "options": ["По месту требования", "Для оформления визы", "В банк", "В налоговую (вычет за обучение)", "По месту работы родителей"]},
      {"name": "language", "label": "Язык справки", "type": "select", "required": True, "options": ["Русский", "Английский"]},
      {"name": "comment", "label": "Комментарий для деканата", "type": "textarea", "required": False, "max": 500}], True, 10),
    ("social_cert", "Справка для соцзащиты или Социального фонда", "certificate", "Для назначения пособий и выплат. Указывается срок обучения и форма.", 2,
     [{"name": "organization", "label": "Организация", "type": "text", "required": True, "max": 200},
      {"name": "comment", "label": "Комментарий", "type": "textarea", "required": False, "max": 500}], True, 20),
    ("military_cert", "Справка в военкомат (форма 26)", "certificate", "Выдаётся только на бумаге с печатью. Забрать в деканате с паспортом.", 3,
     [{"name": "commissariat", "label": "Военный комиссариат", "type": "text", "required": True, "max": 200}], False, 30),
    ("grant_cert", "Справка о стипендии", "certificate", "Размер стипендии за выбранный период.", 3,
     [{"name": "period", "label": "Период", "type": "select", "required": True, "options": ["Последние 3 месяца", "Последние 6 месяцев", "Учебный год"]}], True, 40),
    ("transcript", "Выписка оценок (академическая справка)", "certificate", "Оценки за завершённые семестры по шкале рейтинга, пятибалльной и ECTS.", 5,
     [{"name": "language", "label": "Язык", "type": "select", "required": True, "options": ["Русский", "Английский"]},
      {"name": "comment", "label": "Комментарий", "type": "textarea", "required": False, "max": 500}], True, 50),
    ("individual_plan", "Заявление на индивидуальный график", "statement", "Для совмещения учёбы с работой, спортом, стажировкой или по семейным обстоятельствам.", 10,
     [{"name": "reason", "label": "Причина", "type": "select", "required": True, "options": ["Работа", "Спорт", "Стажировка", "Семейные обстоятельства", "Здоровье"]},
      {"name": "period", "label": "Период", "type": "text", "required": True, "max": 100},
      {"name": "details", "label": "Подробности", "type": "textarea", "required": True, "max": 1500}], False, 60),
    ("retake", "Заявление на пересдачу или перенос сессии", "statement", "Пересдача снижает рейтинг: −10 п.п. за первую и −20 п.п. за вторую.", 5,
     [{"name": "discipline", "label": "Дисциплина", "type": "text", "required": True, "max": 200},
      {"name": "reason", "label": "Причина", "type": "textarea", "required": True, "max": 1500}], False, 70),
    ("dormitory", "Заявление на место в общежитии", "statement", "Рассматривается комиссией по заселению.", 10,
     [{"name": "period", "label": "С какого числа", "type": "date", "required": True},
      {"name": "details", "label": "Обстоятельства", "type": "textarea", "required": False, "max": 1500}], False, 80),
    ("question", "Вопрос в деканат", "question", "Ответ придёт сюда же, в заявку. Без очереди и без почты.", 2,
     [{"name": "topic", "label": "Тема", "type": "select", "required": True,
       "options": ["Расписание", "Оценки и рейтинг", "Стипендия", "Документы", "Оплата обучения", "Другое"]},
      {"name": "text", "label": "Вопрос", "type": "textarea", "required": True, "max": 2000}], False, 90),
]


def _dt(d: date, hh: int, mm: int = 0):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=MSK)


def run(conn, today: date = None, passwords: dict = None, totp_secret: str = None, verbose=True):
    """очистить и заполнить базу демо-данными; -> {логин: пароль}, секрет TOTP"""
    rnd = random.Random(2026)
    today = today or datetime.now(MSK).date()
    passwords = dict(passwords or json.loads(os.environ.get("LK_DEMO_PASSWORDS") or "{}"))
    totp_secret = totp_secret or os.environ.get("LK_DEMO_TOTP_SECRET") or pyotp.random_base32()
    for login in [s[0] for s in STUDENTS] + [STAFF[0]]:
        passwords.setdefault(login, "-".join(secrets.token_urlsafe(4) for _ in range(3)))
    with conn.transaction():
        conn.execute("""TRUNCATE faculties, users, semesters, groups, teachers, disciplines, request_types, rate_limits, login_attempts,
            audit_log RESTART IDENTITY CASCADE""")
        fac = {}
        for code, name, scheme, office, phone, email in FACULTIES:
            fac[code] = conn.execute("""INSERT INTO faculties (code, name, pair_scheme, dean_office, dean_phone, dean_email)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""", (code, name, scheme, office, phone, email)).fetchone()["id"]
        # семестры
        sem = {}
        sem_rows = [("2024-1", "Осенний семестр 2024/25", date(2024, 9, 2), date(2024, 12, 22), date(2025, 1, 9), date(2025, 1, 31)),
                    ("2024-2", "Весенний семестр 2024/25", date(2025, 2, 10), date(2025, 5, 31), date(2025, 6, 9), date(2025, 6, 30)),
                    ("2025-1", "Осенний семестр 2025/26", date(2025, 9, 1), date(2025, 12, 21), date(2026, 1, 9), date(2026, 1, 31)),
                    ("2025-2", "Весенний семестр 2025/26", date(2026, 2, 9), date(2026, 5, 31), date(2026, 6, 8), date(2026, 6, 30)),
                    ("2026-1", "Осенний семестр 2026/27", date(2026, 9, 1), date(2026, 12, 20), date(2027, 1, 11), date(2027, 1, 30))]
        for code, title, s, e, ss, se in sem_rows:
            sem[code] = conn.execute("""INSERT INTO semesters (code, title, starts_on, ends_on, session_from, session_to, is_current)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""", (code, title, s, e, ss, se, code == "2026-1")).fetchone()["id"]
        cur_sem = sem["2026-1"]
        sem_start, sem_end = date(2026, 9, 1), date(2026, 12, 20)
        # группы
        grp = {}
        all_groups = set(CURRENT) | {g for v in STREAM.values() for g in v}
        for code in sorted(all_groups):
            faculty_code = code.split("-")[0]
            course = int(code.split("-")[1])
            if faculty_code in fac:
                kind, language, f_id = "academic", None, fac[faculty_code]
            else:
                kind = "language"
                language = {"АНГЛ": "Английский", "НЕМ": "Немецкий", "ФР": "Французский", "ИСП": "Испанский"}[faculty_code]
                owner = next(s for s in STUDENTS if any(lg == code for lg, _ in s[7]))
                f_id = fac[owner[2]]
            grp[code] = conn.execute("INSERT INTO groups (faculty_id, code, kind, course, language) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                                     (f_id, code, kind, course, language)).fetchone()["id"]
        teacher = {k: conn.execute("INSERT INTO teachers (full_name, title) VALUES (%s, %s) RETURNING id", v).fetchone()["id"]
                   for k, v in TEACHERS.items()}
        disc = {}

        def discipline_id(name):
            if name not in disc:
                disc[name] = conn.execute("INSERT INTO disciplines (name) VALUES (%s) RETURNING id", (name,)).fetchone()["id"]
            return disc[name]

        # пользователи
        users = {}
        for login, (last, first, middle), fcode, program, profile, course, group, langs, funding, year, advisor in STUDENTS:
            uid = conn.execute("""INSERT INTO users (public_id, login, password_hash, role, demo) VALUES (%s, %s, %s, 'student', true)
                RETURNING id""", (public_id(), login, hash_password(passwords[login]))).fetchone()["id"]
            users[login] = uid
            rb = f"{str(year)[2:]}-{fcode}-{rnd.randint(1000, 9999)}"
            conn.execute("""INSERT INTO students (user_id, last_name, first_name, middle_name, faculty_id, program, profile, course, group_id,
                record_book, funding, email, phone, enrolled_year, advisor) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                         (uid, last, first, middle, fac[fcode], program, profile, course, grp[group], rb, funding,
                          f"{login}@student.example.org", f"+7 (000) {rnd.randint(100, 999)}-{rnd.randint(10, 99)}-{rnd.randint(10, 99)}",
                          year, advisor))
            for lg, _ in langs:
                conn.execute("INSERT INTO student_language_groups (student_id, group_id) VALUES (%s, %s)", (uid, grp[lg]))
        s_login, s_name, s_pos, s_facs = STAFF
        sid = conn.execute("""INSERT INTO users (public_id, login, password_hash, role, demo, totp_secret_enc, totp_enabled)
            VALUES (%s, %s, %s, 'staff', true, %s, true) RETURNING id""",
                           (public_id(), s_login, hash_password(passwords[s_login]), encrypt(totp_secret))).fetchone()["id"]
        users[s_login] = sid
        conn.execute("INSERT INTO staff (user_id, full_name, position) VALUES (%s, %s, %s)", (sid, s_name, s_pos))
        for f in s_facs:
            conn.execute("INSERT INTO staff_faculties (staff_id, faculty_id) VALUES (%s, %s)", (sid, fac[f]))

        # текущий семестр: предметы, занятия, оценки
        offering_of = {}
        holidays = {date(2026, 11, 4)}
        for gcode, items in CURRENT.items():
            fcode = gcode.split("-")[0]
            if fcode not in fac:
                owner = next(s for s in STUDENTS if any(lg == gcode for lg, _ in s[7]))
                fcode = owner[2]
            scheme = next(f[2] for f in FACULTIES if f[0] == fcode)
            for name, tkey, control, slots in items:
                d_id = discipline_id(name)
                off = conn.execute("""INSERT INTO offerings (public_id, semester_id, discipline_id, teacher_id, group_id, control, hours)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""", (public_id(), cur_sem, d_id, teacher[tkey], grp[gcode], control,
                                                                          36 * len(slots))).fetchone()["id"]
                offering_of[(gcode, name)] = off
                for wd, pair, kind, room, parity, online in slots:
                    targets = STREAM.get(gcode, [gcode]) if kind == "lecture" else [gcode]
                    d = sem_start
                    while d <= sem_end:
                        if d.weekday() == wd and d not in holidays:
                            wk = (d - (sem_start - timedelta(days=sem_start.weekday()))).days // 7 + 1
                            if parity is None or (parity == "odd") == (wk % 2 == 1):
                                st, en = pair_time(scheme, pair, d)
                                conn.execute("""INSERT INTO lessons (public_id, semester_id, discipline_id, teacher_id, group_ids, kind, starts_at,
                                    ends_at, pair_no, room, building, online_url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                                             (public_id(), cur_sem, d_id, teacher[tkey], [grp[g] for g in targets], kind, st, en, pair,
                                              "" if online else room, "" if online else ADDRESS,
                                              "https://online.example.org/room/" + secrets.token_hex(4) if online else ""))
                        d += timedelta(days=1)
                # сессия: зачёты в последнюю неделю, экзамены в январе с консультацией накануне
                if control == "zachet":
                    zd = date(2026, 12, 14) + timedelta(days=rnd.randint(0, 5))
                    st, en = pair_time(scheme, rnd.choice([2, 3, 4]), zd)
                    conn.execute("""INSERT INTO lessons (public_id, semester_id, discipline_id, teacher_id, group_ids, kind, starts_at, ends_at,
                        room, building) VALUES (%s, %s, %s, %s, %s, 'zachet', %s, %s, %s, %s)""",
                                 (public_id(), cur_sem, d_id, teacher[tkey], [grp[gcode]], st, en, slots[0][3] or "3111", ADDRESS))
        # экзамены: распределяем по датам января, чтобы у группы не было двух в один день
        exam_days = [date(2027, 1, 12), date(2027, 1, 16), date(2027, 1, 20), date(2027, 1, 24), date(2027, 1, 28)]
        for login, *_rest in STUDENTS:
            st_row = next(s for s in STUDENTS if s[0] == login)
            groups_of = [st_row[6]] + [lg for lg, _ in st_row[7]]
            k = 0
            for gcode in groups_of:
                for name, tkey, control, slots in CURRENT[gcode]:
                    if control != "exam":
                        continue
                    day = exam_days[k % len(exam_days)]
                    k += 1
                    d_id = disc[name]
                    conn.execute("""INSERT INTO lessons (public_id, semester_id, discipline_id, teacher_id, group_ids, kind, starts_at, ends_at,
                        room, building) VALUES (%s, %s, %s, %s, %s, 'consult', %s, %s, %s, %s)""",
                                 (public_id(), cur_sem, d_id, teacher[tkey], [grp[gcode]], _dt(day - timedelta(days=1), 12, 0),
                                  _dt(day - timedelta(days=1), 13, 30), "1205", ADDRESS))
                    conn.execute("""INSERT INTO lessons (public_id, semester_id, discipline_id, teacher_id, group_ids, kind, starts_at, ends_at,
                        room, building) VALUES (%s, %s, %s, %s, %s, 'exam', %s, %s, %s, %s)""",
                                 (public_id(), cur_sem, d_id, teacher[tkey], [grp[gcode]], _dt(day, 10, 0), _dt(day, 14, 0),
                                  slots[0][3] or "1205", ADDRESS))
        # оценки текущего семестра
        for login, *_rest in STUDENTS:
            st_row = next(s for s in STUDENTS if s[0] == login)
            for gcode in [st_row[6]] + [lg for lg, _ in st_row[7]]:
                for name, tkey, control, slots in CURRENT[gcode]:
                    s1, s2, bonus = CURRENT_SLICES[login].get(name, (None, None, 0))
                    conn.execute("""INSERT INTO grade_records (student_id, offering_id, slice1, slice2, bonus)
                        VALUES (%s, %s, %s, %s, %s)""", (users[login], offering_of[(gcode, name)], s1, s2, bonus))
        # прошлые семестры
        for login, sems in HISTORY.items():
            st_row = next(s for s in STUDENTS if s[0] == login)
            for code, rows, bonus in sems:
                for name, control, (a, b, c), prem, exam, social, retakes in rows:
                    off = conn.execute("""INSERT INTO offerings (public_id, semester_id, discipline_id, teacher_id, group_id, control)
                        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""", (public_id(), sem[code], discipline_id(name),
                                                                          teacher[rnd.choice(list(TEACHERS))], grp[st_row[6]], control)).fetchone()["id"]
                    conn.execute("""INSERT INTO grade_records (student_id, offering_id, slice1, slice2, slice3, bonus, exam, social, retakes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", (users[login], off, a, b, c, prem, exam, social, retakes))
                if bonus:
                    conn.execute("INSERT INTO semester_bonuses (student_id, semester_id, bonus, reason) VALUES (%s, %s, %s, %s)",
                                 (users[login], sem[code], bonus, "Научная и общественная работа (вымышл.)"))

        _changes(conn, today, grp, users)
        _deadlines(conn, today, fac, grp, users)
        for code, title, category, descr, days, fields, electronic, sort in REQUEST_TYPES:
            conn.execute("""INSERT INTO request_types (code, title, category, description, days, fields, electronic, sort)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", (code, title, category, descr, days, json.dumps(fields, ensure_ascii=False), electronic, sort))
        _requests(conn, today, users, s_name)
        _announcements(conn, today, fac, grp, users, sid)
    if verbose:
        print("Демо-данные загружены. Тестовые аккаунты:")
        for login, pw in passwords.items():
            print(f"  {login:12s} {pw}")
        print(f"  TOTP-секрет сотрудника {s_login}: {totp_secret}")
    return passwords, totp_secret


def _student_groups(conn, uid):
    r = conn.execute("""SELECT s.group_id, array_agg(l.group_id) AS langs FROM students s
        LEFT JOIN student_language_groups l ON l.student_id = s.user_id WHERE s.user_id=%s GROUP BY s.group_id""", (uid,)).fetchone()
    return [r["group_id"]] + [g for g in (r["langs"] or []) if g]


def _lesson_on(conn, groups, day, discipline_like, kind=None):
    return conn.execute("""SELECT l.* FROM lessons l JOIN disciplines d ON d.id = l.discipline_id
        WHERE l.group_ids && %s::int[] AND (l.starts_at AT TIME ZONE 'Europe/Moscow')::date = %s AND d.name LIKE %s
        AND (%s::text IS NULL OR l.kind = %s) ORDER BY l.starts_at LIMIT 1""", (groups, day, discipline_like, kind, kind)).fetchone()


def _next_weekday(d, wd):
    return d + timedelta(days=(wd - d.weekday()) % 7)


def _changes(conn, today, grp, users):
    """несколько переносов и отмен на ближайшие дни, чтобы было что показать"""
    now = datetime.now(MSK)
    anna = _student_groups(conn, users["a.sokolova"])
    dan = _student_groups(conn, users["d.belov"])
    week_start = today - timedelta(days=today.weekday()) + (timedelta(days=7) if today.weekday() >= 5 else timedelta())
    # Анна: семинар ТМО в среду переносится на четверг, 5-я пара, другая аудитория
    wed = week_start + timedelta(days=2)
    l = _lesson_on(conn, anna, wed, "Теория международных%", "seminar")
    if l:
        st, en = pair_time("B", 5, wed + timedelta(days=1))
        conn.execute("""UPDATE lessons SET status='moved', prev_starts_at=starts_at, prev_ends_at=ends_at, prev_room=room, starts_at=%s, ends_at=%s,
            room='3115', change_reason='Преподаватель на научной конференции', changed_at=%s, sequence=sequence+1, updated_at=%s WHERE id=%s""",
                     (st, en, now - timedelta(hours=5), now - timedelta(hours=5), l["id"]))
    # Анна: английский в понедельник — другая аудитория
    mon = week_start
    l = _lesson_on(conn, anna, mon, "Английский%", "language")
    if l:
        conn.execute("""UPDATE lessons SET status='moved', prev_starts_at=starts_at, prev_ends_at=ends_at, prev_room=room, room='1050',
            change_reason='Аудитория 2034 на ремонте', changed_at=%s, sequence=sequence+1, updated_at=%s WHERE id=%s""",
                     (now - timedelta(days=1), now - timedelta(days=1), l["id"]))
    # Анна: лекция по мировой экономике в пятницу отменена
    fri = week_start + timedelta(days=4)
    l = _lesson_on(conn, anna, fri, "Мировая экономика", "lecture")
    if l:
        conn.execute("""UPDATE lessons SET status='cancelled', change_reason='Занятие отменено: лекция будет прочитана онлайн 12 декабря',
            changed_at=%s, sequence=sequence+1, updated_at=%s WHERE id=%s""", (now - timedelta(hours=20), now - timedelta(hours=20), l["id"]))
    # Даниил: лекция по эконометрике во вторник — онлайн
    tue = week_start + timedelta(days=1)
    l = _lesson_on(conn, dan, tue, "Эконометрика", "lecture")
    if l:
        conn.execute("""UPDATE lessons SET status='moved', prev_starts_at=starts_at, prev_ends_at=ends_at, prev_room=room, room='', building='',
            online_url='https://online.example.org/room/econometrics', change_reason='Занятие переведено в онлайн', changed_at=%s,
            sequence=sequence+1, updated_at=%s WHERE id=%s""", (now - timedelta(hours=3), now - timedelta(hours=3), l["id"]))
    # уведомления об изменениях
    for uid, groups in ((users["a.sokolova"], anna), (users["d.belov"], dan)):
        for r in conn.execute("""SELECT l.*, d.name FROM lessons l JOIN disciplines d ON d.id=l.discipline_id
                WHERE l.group_ids && %s::int[] AND l.status <> 'ok' ORDER BY l.changed_at""", (groups,)):
            from .schedule_changes import change_text
            title, body = change_text(r, r["name"])
            conn.execute("""INSERT INTO notifications (public_id, user_id, kind, title, body, link, important, created_at)
                VALUES (%s, %s, 'schedule', %s, %s, %s, true, %s)""", (public_id(), uid, title, body, "/schedule?date=" +
                                                                         r["starts_at"].astimezone(MSK).date().isoformat(), r["changed_at"]))


def _deadlines(conn, today, fac, grp, users):
    rows = [
        (None, fac["МО"], None, "Приём заявлений на повышенную стипендию", "Подайте заявление и подтверждающие документы в деканат или через «Заявки».",
         _dt(today + timedelta(days=8), 17), "admin"),
        ([grp["МО-2-04"]], None, None, "Эссе по теории международных отношений", "Тема — по выбору из списка на семинаре; 2500–3000 слов. Входит в 3-й срез.",
         _dt(today + timedelta(days=12), 23, 59), "study"),
        ([grp["АНГЛ-2-07"]], None, None, "Презентация по английскому языку", "Тема: «Мягкая сила в XXI веке», 7–10 минут.",
         _dt(today + timedelta(days=4), 10, 35), "study"),
        ([grp["МЭО-3-02"]], None, None, "Домашнее задание по эконометрике № 4", "Регрессионный анализ на данных из папки курса.",
         _dt(today + timedelta(days=3), 23, 59), "study"),
        (None, None, users["d.belov"], "Оплата обучения за весенний семестр", "По договору — до 15 января. Квитанция в разделе «Документы» (вымышл.).",
         _dt(date(2027, 1, 15), 23, 59), "payment"),
        (None, fac["МП"], None, "Выбор второго иностранного языка подтверждён", "Изменения языковой группы — только до конца семестра через деканат.",
         _dt(today + timedelta(days=20), 17), "admin"),
        ([grp["МО-2-04"], grp["МЭО-3-02"], grp["МП-1-06"]], None, None, "3-й срез по всем дисциплинам", "Последняя контрольная точка семестра (до 15/16-й недели).",
         _dt(date(2026, 12, 20), 23, 59), "study"),
    ]
    for groups, faculty, student, title, details, due, kind in rows:
        conn.execute("""INSERT INTO deadlines (public_id, group_ids, faculty_id, student_id, title, details, due_at, kind)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", (public_id(), groups, faculty, student, title, details, due, kind))


def _requests(conn, today, users, staff_name):
    from .requests_logic import STATUS_TEXT, add_event, make_certificate, request_number
    now = datetime.now(MSK)
    items = [
        ("a.sokolova", "study_cert", {"purpose": "Для оформления визы", "language": "Английский", "comment": ""}, "electronic",
         [("submitted", 4 * 24 + 3, "student", ""), ("accepted", 4 * 24, "staff", ""), ("ready", 3 * 24 + 20, "staff", "Справка готова — скачайте её в заявке")]),
        ("a.sokolova", "social_cert", {"organization": "Социальный фонд, клиентская служба (вымышл.)", "comment": ""}, "electronic",
         [("submitted", 30, "student", ""), ("accepted", 26, "staff", ""), ("in_progress", 5, "staff", "Уточняем срок обучения в учебном управлении")]),
        ("d.belov", "study_cert", {"purpose": "В налоговую (вычет за обучение)", "language": "Русский", "comment": "Нужна за 2025 год"}, "paper",
         [("submitted", 2, "student", "")]),
        ("d.belov", "individual_plan", {"reason": "Стажировка", "period": "февраль–май 2027", "details": "Стажировка в аналитическом отделе (вымышл.)."},
         "paper", [("submitted", 9 * 24, "student", ""), ("accepted", 8 * 24, "staff", ""),
                   ("rejected", 6 * 24, "staff", "Нужно письмо организации о графике стажировки. Подайте заявление повторно с письмом.")]),
        ("d.belov", "question", {"topic": "Оценки и рейтинг", "text": "Учитывается ли бонус за олимпиаду в рейтинге для скидки на обучение?"}, "electronic",
         [("submitted", 50, "student", ""), ("done", 26, "staff", "Да: бонус за научную и общественную работу (до 5 баллов) прибавляется к рейтингу семестра, а скидка считается по среднему рейтингу за 6 семестров. Пересдачи по-прежнему закрывают скидку.")]),
    ]
    for login, tcode, payload, delivery, events in items:
        t = conn.execute("SELECT * FROM request_types WHERE code=%s", (tcode,)).fetchone()
        created = now - timedelta(hours=events[0][1])
        status = events[-1][0]
        rid = conn.execute("""INSERT INTO requests (public_id, number, student_id, type_code, payload, delivery, status, status_comment, created_at,
            updated_at, due_on) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                           (public_id(), request_number(conn), users[login], tcode, json.dumps(payload, ensure_ascii=False), delivery, status,
                            events[-1][3], created, now - timedelta(hours=events[-1][1]), (created + timedelta(days=t["days"] + 2)).date())).fetchone()["id"]
        for st, hours_ago, role, msg in events:
            add_event(conn, rid, st, msg, role, staff_name if role == "staff" else "", at=now - timedelta(hours=hours_ago))
            if role == "staff":
                conn.execute("""INSERT INTO notifications (public_id, user_id, kind, title, body, link, important, created_at)
                    VALUES (%s, %s, 'request', %s, %s, %s, %s, %s)""", (public_id(), users[login], f"{t['title']}: {STATUS_TEXT[st].lower()}",
                                                                        msg or STATUS_TEXT[st], "/requests", st in ("ready", "rejected"),
                                                                        now - timedelta(hours=hours_ago)))
        if status == "ready" and delivery == "electronic":
            make_certificate(conn, rid, issued_at=now - timedelta(hours=events[-1][1]))


def _announcements(conn, today, fac, grp, users, staff_id):
    from .notify import publish
    now = datetime.now(MSK)
    rows = [
        ("Изменение часов приёма деканата", "С 1 декабря деканат принимает студентов с 10:00 до 16:00, пятница — до 15:00. "
         "Большинство справок теперь можно заказать онлайн в разделе «Заявки» — приходить не нужно.", False, fac["МО"], None, None, 72),
        ("Повышенная стипендия: приём заявлений до конца ноября", "Учитываются научные публикации, конференции и общественная работа за семестр. "
         "Бонус за эту работу (до 5 баллов) также добавляется к академическому рейтингу.", True, fac["МО"], None, None, 30),
        ("Зачётная неделя: 14–19 декабря", "Расписание зачётов появится в разделе «Сессия» и в подключённом календаре. "
         "Напоминаем о правиле 70%: при итоговом балле за семестр от 70% зачёт ставится автоматически.", True, fac["МЭО"], None, None, 50),
        ("Добро пожаловать в цифровой деканат", "Здесь собраны расписание, оценки, заявки и объявления. "
         "Подключите расписание к календарю телефона в разделе «Календарь» — переносы будут приходить сами.", False, fac["МП"], None, None, 90),
        ("Встреча с куратором курса", "Четверг, 15:50, ауд. 1205. Обсудим выбор специализации и рейтинг (вымышл.).", False, fac["МО"], 2, None, 10),
    ]
    for title, body, important, faculty, course, group, hours_ago in rows:
        publish(conn, staff_id, title, body, important, faculty, course, group, at=now - timedelta(hours=hours_ago))


def main():
    from .db import direct, migrate
    with direct() as conn:
        migrate(conn)
        run(conn)


if __name__ == "__main__":
    main()
