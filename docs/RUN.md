# Запуск и развёртывание PirateHunter

Живой сервис: **https://piratehunter.fun**. Инфраструктура: Docker +
docker-compose + Caddy (авто-TLS). Вся система поднимается одной
командой на чистой машине.

## Локальный запуск (docker compose)

Требования: Docker с плагином compose, ~4 ГБ свободной RAM.

```bash
cp .env.example .env        # 1. секреты/конфиг (дефолты рабочие для dev)
docker compose --env-file .env up -d --build   # 2. всё: 4 сервиса + PG×2 + Redis
./scripts/seed.sh           # 3. эталонные демо-данные (302 кандидата, 16 компаний, …)
```

Проверка health:

```bash
curl localhost:64844/health    # backend
curl localhost:51457/health    # core-api
curl localhost:52457/health    # fsp-registry
curl localhost:56151/          # frontend
curl localhost:52457/fsp/v1/profiles/fsp_001   # синтетический профиль ФСП (или 404)
```

OpenAPI backend — **https://api.piratehunter.fun/docs** (живой Swagger на
проде) или локально `http://localhost:64844/docs` (при `BACK_ENV=local`).
Вход по email-коду: без SMTP код пишется в лог backend
(`docker compose logs -f backend`, поле `dev_code`). При
`BACK_AUTH_DEV_LOGIN=1` (dev-дефолт) на `/login` — кнопка входа
демо-аккаунтами без почты: `candidate`, `candidate-fsp`, `employer`.

Порты в dev опубликованы на `127.0.0.1`: 56151 (frontend), 64844
(backend), 51457 (core-api), 52457 (fsp-registry), 55432/55433 (PG),
56379 (Redis) — для отладки и смоука.

## Скрипты scripts/

| Скрипт | Что делает |
|---|---|
| `./scripts/reset-dev.sh` | Стенд в чистое состояние: стоп backend/core, пересоздание схем `ph_back`/`ph_core` (DROP SCHEMA), подъём стека, дожди health. **Данные стираются.** |
| `./scripts/seed.sh` | Ресед эталона (PRD §10) одной командой: детерминированный seed `piratehunter-v1`, truncate доменных таблиц + очистка снапшотов в core. Перед защитой/после тестов жюри база возвращается к эталону. |
| `./scripts/smoke.sh` | Живой сквозной смоук по HTTP (17 шагов): health → dev-login → email-код → профиль → CAT-тест → потребность → shortlist → скрытость контактов → приглашение с вилкой → accept → OIDC-флоу FSP ID → LLM-парсинг → экспресс-тест → рынок вилок → публикация вакансии → отклик → контакты инициатора. Требует поднятый стек, `curl`, `jq`. |

Воспроизводимый цикл: `reset-dev.sh` → `smoke.sh` (зелёный) → `seed.sh`.

## Деплой на VPS (prod)

Целевой стенд: VPS 2 vCPU / 4 ГБ RAM, Ubuntu + Docker + compose-плагин.
В рантайме стек потребляет ~1.5 ГБ — VPS намеренно **не собирает
образы** (сборка Next.js и pip/uv-зависимостей не влезла бы в RAM и
заняла бы десятки минут): образы собираются на домашней машине и
переносятся готовыми.

### Подготовка (один раз)

1. **DNS:** A-записи `piratehunter.fun` (и `www.`) → IP VPS. Для
   мок-OIDC — поддомен `fsp-id.piratehunter.fun` → тот же IP.
2. **На VPS:**
   ```bash
   ufw allow 80,443/tcp && ufw enable      # Caddy выпускает TLS (HTTP-01)
   # ssh-ключ, docker, compose-плагин
   git clone <repo> piratehunter && cd piratehunter
   cp .env.example .env                     # прод-значения (см. ниже)
   ```

### Прод-.env (отличия от dev)

```bash
BACK_ENV=prod                 # /docs закрыт
BACK_AUTH_DEV_LOGIN=0         # dev-login выключен
NEXT_PUBLIC_DEV_LOGIN=0
BACK_JWT_SECRET=<длинная случайная строка>
BACK_CORS_ORIGINS=https://piratehunter.fun
BACK_FSP_PUBLIC_URL=https://fsp-id.piratehunter.fun
BACK_FSP_REDIRECT_URI=https://piratehunter.fun/api/v1/auth/fsp/callback
BACK_FRONT_URL=https://piratehunter.fun
# SMTP (коды на почту): BACK_SMTP_HOST/PORT/USER/PASSWORD/FROM
```

В `Caddyfile` заменить `piratehunter.example.com` → `piratehunter.fun`
и раскомментировать блок `fsp-id.*` (мок-OIDC наружу). Важно:
Caddyfile примонтирован файлом — после правок
`docker compose ... up -d --force-recreate caddy`.

### Перенос образов и старт

```bash
# На домашней машине (сборка):
docker compose --env-file .env build
docker save $(docker compose --env-file .env config --images) | \
  ssh vps 'docker load'

# На VPS:
docker compose --env-file .env up -d     # без --build: образы уже загружены
docker compose ps                        # все healthy
./scripts/seed.sh                        # эталонные демо-данные
```

Caddy сам выпускает и продлевает сертификаты Let's Encrypt (HTTP-01,
порты 80/443), редиректит HTTP→HTTPS, проксирует сайт на frontend, а
`/api/v1` — на backend. core-api наружу не торчит (PRD §4.2).

### Ресед эталона одной командой

```bash
./scripts/seed.sh     # truncate + детерминированная заливка (seed piratehunter-v1)
```

Сводка эталона: 302 кандидата (подтверждённый грейд — 229 ≈ 76%, с
историей ФСП — 181 ≈ 60%), 16 компаний, 6 потребностей, 40 приглашений,
в ранжировании категории backend×middle — 19 кандидатов.

## Тестирование развёртывания

Смоук (`scripts/smoke.sh`) бьёт по `localhost`-портам; на проде
достаточно ручного прохода сквозного сценария из PRD §1 на
`https://piratehunter.fun` + health-чеков. Подробнее — TESTING.md.
