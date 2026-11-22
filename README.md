# Цифровой деканат — личный кабинет студента (концепт)

> **Концепт для конкурса «Цифровой деканат будущего».** Не официальный сервис вуза. Все данные вымышлены, логотипы вуза не используются.

Один кабинет вместо пяти мест: главная «что важно сейчас», расписание с переносами, которое само живёт в календаре телефона
(iPhone, Android, HarmonyOS), успеваемость по рейтинговой системе вуза с подсказкой «сколько нужно на экзамене», заявки и справки
со статусами и PDF с QR-проверкой, уведомления. Для сотрудника деканата — очередь заявок, переносы занятий и объявления.

- Что делает продукт — [docs/SPEC.md](docs/SPEC.md)
- Как устроены вход и защита — [docs/SECURITY.md](docs/SECURITY.md)
- Архитектура — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Как работали с ИИ — [docs/PROCESS_LOG.md](docs/PROCESS_LOG.md), итоговый документ — [docs/process.pdf](docs/process.pdf) (на сайте — `/process.pdf`)

## Запуск на сервере
Чистый сервер Ubuntu/Debian, открыты порты 80 и 443:
```sh
git clone https://github.com/mpcherhse/lkmgimo /opt/lk && cd /opt/lk
sudo sh deploy/bootstrap.sh lk.example.ru   # или без домена — адрес <ip>.sslip.io
```
Скрипт ставит Docker, создаёт `.env` со случайными секретами (только на сервере), запускает Caddy → приложение → PostgreSQL
и при первом запуске заполняет базу вымышленными данными. Caddy сам получает сертификат Let's Encrypt.
Обновление — `git pull && sudo sh deploy/bootstrap.sh` (данные сохраняются). Ручная настройка — по образцу [.env.example](.env.example).

## Разработка
- Бэкенд: Python 3.12, FastAPI, PostgreSQL 17 (psycopg 3), Argon2id, pyotp, icalendar, reportlab.
- Фронтенд: React + TypeScript + Vite, свои CSS-токены, шрифт Onest, иконки Lucide, PWA.
- Тесты: `cd backend && python -m pytest -q tests` (нужна база `lk_test`).
- Правила для ИИ-агентов — [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md).

## Лицензии сторонних материалов
Шрифты PT Sans (ParaType) — в справках, `backend/app/resources/fonts/OFL.txt`, и Onest — в интерфейсе; оба SIL OFL 1.1. Иконки Lucide (ISC). Список частых паролей — SecLists (MIT).
