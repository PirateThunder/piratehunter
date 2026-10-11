#!/usr/bin/env bash
# PirateHunter — ресед демо-стенда в эталонное состояние (PRD §10).
# Детерминированно (seed "piratehunter-v1"): 302 кандидата, 16 компаний,
# 6 потребностей, 40 приглашений, снапшоты в core. Данные стираются!
# Запуск: ./scripts/seed.sh   (стек должен быть поднят)
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T backend \
  uv run --frozen --no-dev python -m app.seeds
