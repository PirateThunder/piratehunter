#!/usr/bin/env bash
# PirateHunter — деплой на VPS с переносом ГОТОВЫХ образов (VPS не собирает).
# VPS: 2 vCPU / 4 ГБ RAM / 40+ ГБ NVMe, Ubuntu 24.04, публичный IP.
# Использование: ./scripts/deploy-vps.sh <user@host> [ssh-порт]
# Перед запуском: A-записи piratehunter.fun и fsp-id.piratehunter.fun → IP VPS
# (Caddy сам возьмёт TLS у Let's Encrypt).
set -euo pipefail
cd "$(dirname "$0")/.."

HOST="${1:?usage: deploy-vps.sh user@host [port]}"
PORT="${2:-22}"
SSH="ssh -p $PORT -o StrictHostKeyChecking=accept-new $HOST"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "== 1/7 Проверка локального стека (образы должны быть свежие) =="
docker compose config -q
for img in piratehunter-backend piratehunter-core-api piratehunter-fsp-registry piratehunter-frontend; do
  docker image inspect "$img" >/dev/null 2>&1 || docker compose build
done

echo "== 2/7 Перенос образов (docker save | ssh docker load) =="
IMAGES=$(docker compose config --images)
docker save $IMAGES | gzip -1 | $SSH 'docker load' && echo "образы на месте"

echo "== 3/7 Код на сервер (rsync, без мусора) =="
rsync -az --delete -e "ssh -p $PORT" \
  --exclude .git --exclude .env --exclude 'node_modules' --exclude '.venv' \
  --exclude 'materials' --exclude 'deliverables/demo-video/scenes' \
  --exclude 'deliverables/demo-video/build' --exclude '**/__pycache__' \
  ./ "$HOST:/opt/piratehunter/"

echo "== 4/7 Docker на VPS (если нет) + firewall =="
$SSH 'command -v docker >/dev/null || (curl -fsSL https://get.docker.com | sh); \
  (ufw allow 22,80,443/tcp >/dev/null 2>&1 || true)'

echo "== 5/7 .env на сервере (секреты генерируются, dev-login ВКЛ для жюри) =="
$SSH 'cd /opt/piratehunter && [ -f .env ] || { \
  sed -e "s/^BACK_DB_PASSWORD=.*/BACK_DB_PASSWORD=$(openssl rand -hex 16)/" \
      -e "s/^CORE_DB_PASSWORD=.*/CORE_DB_PASSWORD=$(openssl rand -hex 16)/" \
      -e "s/^BACK_JWT_SECRET=.*/BACK_JWT_SECRET=$(openssl rand -hex 32)/" \
      .env.example > .env; }'

echo "== 6/7 Запуск стека (base + prod override с Caddy) =="
$SSH "cd /opt/piratehunter && $COMPOSE up -d && sleep 8 && $COMPOSE ps --format 'table {{.Name}}\t{{.Status}}'"

echo "== 7/7 Засев эталона =="
$SSH "cd /opt/piratehunter && docker compose exec -T backend \
  uv run --frozen --no-dev python -m app.seeds" || echo "WARN: сид не прошёл — смотри логи: $SSH 'cd /opt/piratehunter && docker compose logs backend --tail 50'"

echo
echo "Готово. Проверки (TLS выпустится через ~30–60 с после появления A-записи):"
echo "  curl -sI https://piratehunter.fun/ | head -3"
echo "  curl -s https://piratehunter.fun/api/v1/catalog | head -c 200   (через прокси фронта)"
echo "  curl -sI https://fsp-id.piratehunter.fun/health"
echo "  Логи: $SSH 'cd /opt/piratehunter && docker compose logs -f --tail 50'"
echo "  Ресед после жюри: $SSH 'cd /opt/piratehunter && docker compose exec -T backend uv run --frozen --no-dev python -m app.seeds'"
