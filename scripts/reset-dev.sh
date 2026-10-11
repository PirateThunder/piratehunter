#!/usr/bin/env bash
# PirateHunter — сброс dev-стенда в чистое состояние (ph_back + ph_core).
# Пересоздаёт схемы, прогоняет миграции, перезапускает сервисы.
# ТОЛЬКО для локальной разработки/демо — данные стираются безвозвратно.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Останавливаю backend и core-api =="
docker compose stop backend core-api >/dev/null

echo "== Пересоздаю схемы ph_back и ph_core =="
docker compose exec -T pg-back psql -U ph -d ph_back \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' >/dev/null
docker compose exec -T pg-core psql -U ph -d ph_core \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' >/dev/null

echo "== Поднимаю стек (миграции backend → сервисы) =="
docker compose up -d >/dev/null

echo "== Жду health =="
for url in http://localhost:64844/health http://localhost:51457/health \
           http://localhost:52457/health http://localhost:56151/; do
  for i in $(seq 1 60); do
    curl -sf -o /dev/null "$url" && break
    [ "$i" = 60 ] && { echo "FAIL: $url не ожил"; exit 1; }
    sleep 2
  done
done
echo "OK: стенд в чистом состоянии"
