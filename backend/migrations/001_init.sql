-- Схема прототипа «Цифровой деканат». Все данные в базе вымышленные.
-- Публичные идентификаторы (public_id) случайные: по ним нельзя перебрать чужие записи.

CREATE TABLE faculties (
    id          serial PRIMARY KEY,
    code        text NOT NULL UNIQUE,          -- МО, МЭО, МП ...
    name        text NOT NULL,
    pair_scheme text NOT NULL CHECK (pair_scheme IN ('A', 'B')),   -- время пар зависит от факультета
    dean_office text NOT NULL DEFAULT '',      -- кабинет и часы приёма
    dean_phone  text NOT NULL DEFAULT '',
    dean_email  text NOT NULL DEFAULT ''
);

CREATE TABLE users (
    id                   bigserial PRIMARY KEY,
    public_id            text NOT NULL UNIQUE,
    login                text NOT NULL UNIQUE,
    password_hash        text NOT NULL,
    role                 text NOT NULL CHECK (role IN ('student', 'staff')),
    active               boolean NOT NULL DEFAULT true,
    demo                 boolean NOT NULL DEFAULT false,   -- общий тестовый аккаунт жюри: пароль и 2FA не меняются
    must_change_password boolean NOT NULL DEFAULT false,
    totp_secret_enc      text,                             -- секрет TOTP, зашифрован AES-GCM ключом сервера
    totp_enabled         boolean NOT NULL DEFAULT false,
    totp_last_step       bigint,                           -- защита от повторного использования кода
    session_ttl_days     integer NOT NULL DEFAULT 30,
    created_at           timestamptz NOT NULL DEFAULT now(),
    last_login_at        timestamptz
);

CREATE TABLE semesters (
    id            serial PRIMARY KEY,
    code          text NOT NULL UNIQUE,    -- 2026-1
    title         text NOT NULL,
    starts_on     date NOT NULL,
    ends_on       date NOT NULL,           -- последний день занятий
    session_from  date NOT NULL,
    session_to    date NOT NULL,
    is_current    boolean NOT NULL DEFAULT false
);

CREATE TABLE groups (
    id          serial PRIMARY KEY,
    faculty_id  integer NOT NULL REFERENCES faculties(id),
    code        text NOT NULL UNIQUE,
    kind        text NOT NULL CHECK (kind IN ('academic', 'language')),
    course      integer NOT NULL,
    language    text                       -- для языковых групп
);

CREATE TABLE students (
    user_id        bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    last_name      text NOT NULL,
    first_name     text NOT NULL,
    middle_name    text NOT NULL DEFAULT '',
    faculty_id     integer NOT NULL REFERENCES faculties(id),
    program        text NOT NULL,          -- направление подготовки
    profile        text NOT NULL DEFAULT '',
    level          text NOT NULL DEFAULT 'Бакалавриат',
    course         integer NOT NULL,
    group_id       integer NOT NULL REFERENCES groups(id),
    record_book    text NOT NULL,          -- номер зачётной книжки (вымышленный)
    funding        text NOT NULL CHECK (funding IN ('budget', 'contract')),
    email          text NOT NULL,
    phone          text NOT NULL DEFAULT '',
    enrolled_year  integer NOT NULL,
    advisor        text NOT NULL DEFAULT ''
);

CREATE TABLE student_language_groups (
    student_id bigint NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
    group_id   integer NOT NULL REFERENCES groups(id),
    PRIMARY KEY (student_id, group_id)
);

CREATE TABLE staff (
    user_id     bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name   text NOT NULL,
    position    text NOT NULL
);

CREATE TABLE staff_faculties (
    staff_id   bigint NOT NULL REFERENCES staff(user_id) ON DELETE CASCADE,
    faculty_id integer NOT NULL REFERENCES faculties(id),
    PRIMARY KEY (staff_id, faculty_id)
);

CREATE TABLE teachers (
    id        serial PRIMARY KEY,
    full_name text NOT NULL,              -- вымышленные
    title     text NOT NULL DEFAULT ''
);

CREATE TABLE disciplines (
    id     serial PRIMARY KEY,
    name   text NOT NULL,
    short  text NOT NULL DEFAULT ''
);

-- Дисциплина в семестре у конкретной группы: форма контроля и преподаватель
CREATE TABLE offerings (
    id            serial PRIMARY KEY,
    public_id     text NOT NULL UNIQUE,
    semester_id   integer NOT NULL REFERENCES semesters(id),
    discipline_id integer NOT NULL REFERENCES disciplines(id),
    teacher_id    integer REFERENCES teachers(id),
    group_id      integer NOT NULL REFERENCES groups(id),
    control       text NOT NULL CHECK (control IN ('exam', 'zachet')),
    hours         integer NOT NULL DEFAULT 0
);

-- Занятия: конкретные даты. Перенос меняет строку, прежнее время хранится в prev_*
CREATE TABLE lessons (
    id            bigserial PRIMARY KEY,
    public_id     text NOT NULL UNIQUE,
    semester_id   integer NOT NULL REFERENCES semesters(id),
    discipline_id integer NOT NULL REFERENCES disciplines(id),
    teacher_id    integer REFERENCES teachers(id),
    group_ids     integer[] NOT NULL,              -- поток: несколько академических групп; или одна языковая
    kind          text NOT NULL CHECK (kind IN ('lecture', 'seminar', 'language', 'consult', 'exam', 'zachet', 'event')),
    starts_at     timestamptz NOT NULL,
    ends_at       timestamptz NOT NULL,
    pair_no       integer,
    room          text NOT NULL DEFAULT '',
    building      text NOT NULL DEFAULT '',
    online_url    text NOT NULL DEFAULT '',
    status        text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'moved', 'cancelled')),
    prev_starts_at timestamptz,
    prev_ends_at   timestamptz,
    prev_room      text,
    change_reason  text,
    changed_at     timestamptz,
    sequence       integer NOT NULL DEFAULT 0,     -- для календарей: растёт при каждом изменении
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX lessons_groups ON lessons USING gin (group_ids);
CREATE INDEX lessons_starts ON lessons (starts_at);

-- Успеваемость по системе академического рейтинга (Р = 0,4·Б1 + 0,5·Б2 + 0,1·Б3)
CREATE TABLE grade_records (
    id           bigserial PRIMARY KEY,
    student_id   bigint NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
    offering_id  integer NOT NULL REFERENCES offerings(id),
    slice1       numeric(5,2),
    slice2       numeric(5,2),
    slice3       numeric(5,2),
    bonus        numeric(5,2) NOT NULL DEFAULT 0,  -- премия преподавателя, не более 10 п.п.
    exam         numeric(5,2),                      -- Б2: экзамен или зачёт (фактическая оценка)
    social       numeric(5,2),                      -- Б3
    retakes      integer NOT NULL DEFAULT 0,
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (student_id, offering_id)
);

CREATE TABLE semester_bonuses (
    student_id  bigint NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
    semester_id integer NOT NULL REFERENCES semesters(id),
    bonus       numeric(4,2) NOT NULL CHECK (bonus BETWEEN 0 AND 5),
    reason      text NOT NULL DEFAULT '',
    PRIMARY KEY (student_id, semester_id)
);

CREATE TABLE deadlines (
    id          bigserial PRIMARY KEY,
    public_id   text NOT NULL UNIQUE,
    group_ids   integer[],                   -- NULL — для всех на факультете faculty_id
    faculty_id  integer REFERENCES faculties(id),
    student_id  bigint REFERENCES students(user_id) ON DELETE CASCADE,   -- личный дедлайн (например, оплата по договору)
    title       text NOT NULL,
    details     text NOT NULL DEFAULT '',
    due_at      timestamptz NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('study', 'admin', 'payment')),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Заявки и справки
CREATE TABLE request_types (
    code         text PRIMARY KEY,
    title        text NOT NULL,
    category     text NOT NULL CHECK (category IN ('certificate', 'statement', 'question')),
    description  text NOT NULL,
    days         integer NOT NULL,            -- срок исполнения, рабочих дней
    fields       jsonb NOT NULL DEFAULT '[]', -- описание полей формы
    electronic   boolean NOT NULL DEFAULT false,   -- можно получить электронно с QR-проверкой
    sort         integer NOT NULL DEFAULT 0
);

CREATE TABLE requests (
    id           bigserial PRIMARY KEY,
    public_id    text NOT NULL UNIQUE,
    number       text NOT NULL UNIQUE,        -- человекочитаемый номер З-2026-000123
    student_id   bigint NOT NULL REFERENCES students(user_id) ON DELETE CASCADE,
    type_code    text NOT NULL REFERENCES request_types(code),
    payload      jsonb NOT NULL DEFAULT '{}',
    delivery     text NOT NULL CHECK (delivery IN ('electronic', 'paper')),
    copies       integer NOT NULL DEFAULT 1,
    status       text NOT NULL CHECK (status IN ('submitted', 'accepted', 'in_progress', 'ready', 'done', 'rejected', 'cancelled')),
    status_comment text NOT NULL DEFAULT '',
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    due_on       date
);
CREATE INDEX requests_student ON requests (student_id, created_at DESC);

CREATE TABLE request_events (
    id          bigserial PRIMARY KEY,
    request_id  bigint NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    at          timestamptz NOT NULL DEFAULT now(),
    status      text,
    message     text NOT NULL DEFAULT '',
    author_role text NOT NULL CHECK (author_role IN ('student', 'staff', 'system')),
    author_name text NOT NULL DEFAULT ''
);

CREATE TABLE certificates (
    id           bigserial PRIMARY KEY,
    request_id   bigint NOT NULL UNIQUE REFERENCES requests(id) ON DELETE CASCADE,
    number       text NOT NULL UNIQUE,
    verify_code  text NOT NULL UNIQUE,       -- случайный код для QR
    issued_at    timestamptz NOT NULL DEFAULT now(),
    valid_until  date,
    revoked_at   timestamptz
);

-- Объявления деканата и личные уведомления
CREATE TABLE announcements (
    id          bigserial PRIMARY KEY,
    public_id   text NOT NULL UNIQUE,
    title       text NOT NULL,
    body        text NOT NULL,
    important   boolean NOT NULL DEFAULT false,
    faculty_id  integer REFERENCES faculties(id),
    course      integer,
    group_id    integer REFERENCES groups(id),
    author_id   bigint REFERENCES users(id),
    published_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE notifications (
    id          bigserial PRIMARY KEY,
    public_id   text NOT NULL UNIQUE,
    user_id     bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('announcement', 'schedule', 'request', 'deadline', 'grade', 'security')),
    title       text NOT NULL,
    body        text NOT NULL DEFAULT '',
    link        text NOT NULL DEFAULT '',
    important   boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    read_at     timestamptz
);
CREATE INDEX notifications_user ON notifications (user_id, created_at DESC);

-- Календари: ссылка-подписка (ICS) и пароли приложений (CalDAV)
CREATE TABLE calendar_feeds (
    id           bigserial PRIMARY KEY,
    user_id      bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   text NOT NULL UNIQUE,
    token_hint   text NOT NULL,              -- последние 4 символа, чтобы узнать ссылку в списке
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    revoked_at   timestamptz
);

CREATE TABLE app_passwords (
    id           bigserial PRIMARY KEY,
    public_id    text NOT NULL UNIQUE,
    user_id      bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label        text NOT NULL,
    secret_hash  text NOT NULL UNIQUE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    last_client  text,
    revoked_at   timestamptz
);

-- ---------- вход, устройства, сеансы ----------
CREATE TABLE devices (
    id            bigserial PRIMARY KEY,
    user_id       bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash      text NOT NULL,
    label         text NOT NULL DEFAULT '',
    ua_family     text NOT NULL DEFAULT '',
    os            text NOT NULL DEFAULT '',
    model         text NOT NULL DEFAULT '',
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, key_hash)
);

CREATE TABLE sessions (
    id              bigserial PRIMARY KEY,
    public_id       text NOT NULL UNIQUE,
    user_id         bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id       bigint REFERENCES devices(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_active_at  timestamptz NOT NULL DEFAULT now(),
    last_ip         text NOT NULL DEFAULT '',
    ua_json         jsonb NOT NULL DEFAULT '{}',
    mfa_passed      boolean NOT NULL DEFAULT false,
    sudo_until      timestamptz,
    ttl_days        integer NOT NULL DEFAULT 30,
    challenge_at    timestamptz,
    revoked_at      timestamptz,
    revoke_reason   text,
    revoked_by_session_id bigint
);
CREATE INDEX sessions_user ON sessions (user_id) WHERE revoked_at IS NULL;

CREATE TABLE session_tokens (
    token_hash    text PRIMARY KEY,
    session_id    bigint NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    issued_at     timestamptz NOT NULL DEFAULT now(),
    first_seen_at timestamptz,
    superseded_at timestamptz
);
CREATE INDEX session_tokens_session ON session_tokens (session_id);

-- вход в два шага: пароль верный, ждём код 2FA
CREATE TABLE mfa_challenges (
    token_hash  text PRIMARY KEY,
    user_id     bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    attempts    integer NOT NULL DEFAULT 0
);

CREATE TABLE login_events (
    id           bigserial PRIMARY KEY,
    user_id      bigint REFERENCES users(id) ON DELETE CASCADE,
    login        text NOT NULL,
    at           timestamptz NOT NULL DEFAULT now(),
    ip           text NOT NULL DEFAULT '',
    device_label text NOT NULL DEFAULT '',
    result       text NOT NULL,
    reason       text,
    session_id   bigint
);
CREATE INDEX login_events_user ON login_events (user_id, at DESC);

CREATE TABLE security_events (
    id          bigserial PRIMARY KEY,
    user_id     bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    at          timestamptz NOT NULL DEFAULT now(),
    kind        text NOT NULL,
    session_id  bigint,
    details     jsonb NOT NULL DEFAULT '{}'
);

-- блокировка входа: по паре «логин + адрес», чтобы чужие ошибки не запирали аккаунт для всех
CREATE TABLE login_attempts (
    key        text PRIMARY KEY,
    failures   integer NOT NULL DEFAULT 0,
    lock_until timestamptz
);

CREATE TABLE rate_limits (
    key          text PRIMARY KEY,
    window_start double precision NOT NULL,
    count        integer NOT NULL
);

CREATE TABLE audit_log (
    id       bigserial PRIMARY KEY,
    at       timestamptz NOT NULL DEFAULT now(),
    user_id  bigint,
    action   text NOT NULL,
    target   text,
    details  jsonb
);
