#!/bin/sh
# Ночная копия базы (cron: 0 3 * * * /opt/lk/deploy/backup.sh). Хранит 7 последних копий.
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
docker compose exec -T db pg_dump -U lk -Fc lk > "backups/lk-$(date +%F).dump"
ls -1t backups/lk-*.dump | tail -n +8 | xargs -r rm -f
