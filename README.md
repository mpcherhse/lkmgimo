# Цифровой деканат — личный кабинет студента (концепт)

> **Концепт для конкурса «Цифровой деканат будущего».** Не официальный сервис вуза. Все данные вымышлены, логотипы вуза не используются.

Один кабинет вместо пяти мест: главная «что важно сейчас», расписание с переносами, которое само живёт в календаре телефона
(iPhone, Android, HarmonyOS), успеваемость по рейтинговой системе вуза с подсказкой «сколько нужно на экзамене», заявки и справки
со статусами и PDF с QR-проверкой, уведомления. Для сотрудника деканата — очередь заявок, переносы занятий и объявления.

- Что делает продукт — [docs/SPEC.md](docs/SPEC.md)
- Как устроены вход и защита — [docs/SECURITY.md](docs/SECURITY.md)
- Архитектура — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Как работали с ИИ — [docs/PROCESS_LOG.md](docs/PROCESS_LOG.md)

## Запуск на сервере
```sh
cp .env.example .env        # заполнить: домен, LK_SECRET_KEY, POSTGRES_PASSWORD, пароли демо-аккаунтов
docker compose up -d --build
docker compose exec app python -m app.cli seed
```
Caddy сам получит сертификат Let's Encrypt для `LK_DOMAIN`.

## Разработка
- Бэкенд: Python 3.12, FastAPI, PostgreSQL 17 (psycopg 3), Argon2id, pyotp, icalendar, reportlab.
- Фронтенд: React + TypeScript + Vite, свои CSS-токены, PWA.
- Тесты: `cd backend && python -m pytest -q tests` (нужна база `lk_test`).
- Правила для ИИ-агентов — [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md).

## Лицензии сторонних материалов
Шрифт PT Sans (ParaType, SIL OFL 1.1) — `backend/app/resources/fonts/OFL.txt`. Список частых паролей — SecLists (MIT).
