#!/bin/sh
# Первый запуск стенда на чистом сервере Ubuntu/Debian.
#   sudo sh deploy/bootstrap.sh lk.example.ru      — свой домен (A-запись уже указывает на сервер)
#   sudo sh deploy/bootstrap.sh                     — без домена: <ip>.sslip.io
# Создаёт .env со случайными секретами (если его ещё нет), собирает и запускает контейнеры, при первом запуске заполняет базу демо-данными.
# Повторный запуск — обновление: пересобирает приложение, данные не трогает.
set -eu
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq ca-certificates curl
  curl -fsSL https://get.docker.com | sh
fi

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  IP=$(curl -fsS4 https://ifconfig.me || hostname -I | awk '{print $1}')
  DOMAIN="$(echo "$IP" | tr . -).sslip.io"
fi

FIRST=0
rnd() { head -c "$1" /dev/urandom | base64 | tr -d '/+=\n' | cut -c1-"$2"; }
if [ ! -f .env ]; then
  umask 077
  cat > .env <<EOF
LK_PUBLIC_URL=https://$DOMAIN
LK_DOMAIN=$DOMAIN
LK_SECRET_KEY=$(head -c 32 /dev/urandom | base64)
POSTGRES_PASSWORD=$(rnd 48 40)
LK_DEMO_PASSWORDS={"a.sokolova":"Sokolova-$(rnd 9 6)","d.belov":"Belov-$(rnd 9 6)","m.kovaleva":"Kovaleva-$(rnd 9 6)","dekanat":"Dekanat-$(rnd 9 6)"}
LK_DEMO_TOTP_SECRET=$(head -c 20 /dev/urandom | base32 | tr -d '=\n')
LK_DEMO_TOTP_HELPER=1
EOF
  echo ".env создан (секреты только на этом сервере)"
  FIRST=1
fi

docker compose up -d --build
# ждём, пока приложение применит миграции
for i in $(seq 1 60); do
  docker compose exec -T app python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8800/api/health')" >/dev/null 2>&1 && break
  sleep 2
done
# демо-данные — только при первом запуске (seed стирает всё, что ввели пользователи)
[ "$FIRST" = 1 ] && docker compose exec -T app python -m app.cli seed
echo
echo "Готово: https://$DOMAIN"
grep '^LK_DEMO_PASSWORDS' .env
