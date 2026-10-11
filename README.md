# PirateHunter

Платформа подбора ИТ-специалистов с **обратной механикой**: работодатель
находит кандидата сам. Кандидаты автоматически категоризуются по
объективно подтверждаемому профилю — опрос по специализации, адаптивный
CAT-тест на заявленный грейд (грейд = результат теста, не стаж),
достижения ФСП — и попадают в категоризованную базу (7 специализаций ×
4 грейда). Работодатель описывает потребность, получает объяснимую
подборку («почему этот человек» — разложение score по факторам) и
направляет конкретному кандидату приглашение **с обязательной зарплатной
вилкой**. Контакты кандидата раскрываются только после принятия
приглашения. Достижения ФСП влияют на ранжирование внутри категории,
но не на грейд; кейс «нет истории ФСП» — первоклассный: профиль
показывается со статусом, участвует в подборке без буста.

Кейс ФСП (ЛЦТ 2026, спец. трек). **Живой сервис: https://piratehunter.fun**.
Репозиторий: https://github.com/piratehunter-team/piratehunter
(плейсхолдер — заменить на публичный к сдаче). Источник правды по
продукту — [PRD.md](PRD.md); материалы кейса (ТЗ, брендбук) — в
`materials/` (не в git). Техническая документация — [docs/](docs/)
(ARCHITECTURE, RUN, TESTING, VALIDATION, MATCHING, FSP-INTEGRATION, API;
единый PDF собирается `docs/build_docs.py`).

**Стек:** Python 3.13 · FastAPI · Pydantic v2 · SQLAlchemy 2 (async) ·
Alembic · PostgreSQL 16 ×2 · Redis 7 · numpy (IRT) · OpenRouter LLM
(Qwen-класс, с fallback) · Next.js 16 (App Router, FSD) · Bun ·
Tailwind v4 · zustand · Docker · Caddy · pytest/ruff/biome.

## Быстрый старт

```bash
cp .env.example .env                               # 1. конфиг (дефолты для dev)
docker compose --env-file .env up -d --build       # 2. всё: 4 сервиса + PG×2 + Redis
./scripts/seed.sh                                  # 3. эталонные демо-данные
```

Открыть http://localhost:56151. OpenAPI backend — http://localhost:64844/docs
(`BACK_ENV=local`). Сквозной смоук: `./scripts/smoke.sh` (14 шагов по
живому стеку), сброс стенда: `./scripts/reset-dev.sh`. Подробно —
[docs/RUN.md](docs/RUN.md).

## Демо-аккаунты (dev-login)

На `/login` — кнопка входа без почты (`BACK_AUTH_DEV_LOGIN=1`, dev-дефолт;
эквивалент API: `POST /api/v1/auth/dev {"account": "<имя>"}`):

| Аккаунт | Роль | Что показывает |
|---|---|---|
| `candidate` | Кандидат | Без истории ФСП (обязательный кейс «404») |
| `candidate-fsp` | Кандидат | С привязанным ФСП ID `fsp_001` — богатая история достижений |
| `employer` | Работодатель | Потребность → подборка с explanation → приглашение с вилкой |

Вход через FSP ID: кнопка «Войти через FSP ID» на `/login` проходит
полный мок-OIDC флоу (fsp_001 → тот же демо-аккаунт `candidate-fsp`).
Экспресс-тест для жюри — 4 вопроса, 3–5 минут.

## Архитектура

Монорепо, четыре сервиса, общение только по HTTP, ноль shared-кода.
Персональные данные живут только в backend; core-api оперирует
анонимными `candidate_id` (privacy by design). Internal-сервисы наружу
не выставлены — с ними общается только backend внутри docker-сети.

| Сервис | Порт | Назначение | Наружу |
|---|---|---|---|
| `frontend` | 56151 | Next.js (FSD): лендинг + ЛК кандидата + ЛК работодателя | да (через Caddy) |
| `backend` | 64844 | FastAPI `/api/v1`: auth (email-код, FSP ID, dev-login), профили, ПДн, приглашения | да (`/api/v1`) |
| `core-api` | 51457 | FastAPI internal: тест-движок (CAT-lite), матчинг с explanation, каталог | нет |
| `fsp-registry` | 52457 | FastAPI internal: мок-реестр достижений ФСП + мок-OIDC «FSP ID» | нет* |
| `pg-back` / `pg-core` | — | PostgreSQL 16, БД `ph_back` / `ph_core` | нет |
| `redis` | — | Redis 7: коды auth, OIDC state, кэш | нет |

\* В проде authorize-страница мок-OIDC доступна браузеру отдельным
поддоменом `fsp-id.*` (см. `Caddyfile`). В dev порты опубликованы на
`127.0.0.1` для отладки (у PG/Redis — 55432/55433/56379). Деплой на VPS
(2 vCPU/4 ГБ): образы переносятся готовыми `docker save | ssh docker load`
— [docs/RUN.md](docs/RUN.md).

## Качество

202 автотеста (hunter_core 75 · backend 110 · fsp_registry 17), живой
смоук 14 шагов, воспроизводимый цикл reset→smoke→seed, детерминированные
сиды (302 кандидата / 16 компаний / 6 потребностей / 40 приглашений).
Валидация (PRD §9): стабильность грейда 96.7% (порог 80%), ±1 — 100%
(порог 97%), Spearman 0.972 (порог 0.85), Precision@5 0.85 (порог 0.8);
полный прогон 300×3: 99% / 0.977 — [docs/VALIDATION.md](docs/VALIDATION.md).

## Структура

```
piratehunter/
├── PRD.md               # источник правды по продукту
├── README.md
├── docker-compose.yml   # стек: 4 сервиса + PG×2 + Redis (+ back-migrate)
├── Caddyfile            # прод: TLS (Let's Encrypt), reverse proxy
├── .env.example
├── docs/                # техническая документация (ARCHITECTURE, RUN,
│                        #   TESTING, VALIDATION, MATCHING,
│                        #   FSP-INTEGRATION, API + build_docs.py → PDF)
├── backend/             # FastAPI · /api/v1 · ПДн · Alembic · pytest
├── hunter_core/         # core-api · engine/ (CAT, скоринг) · itembank/ ·
│                        #   validation/ (харнесс §9) · llm/
├── fsp_registry/        # мок-реестр достижений ФСП + мок-OIDC (stateless)
├── frontend/            # Next.js 16 FSD · айдентика ФСП (tokens.fsp.css)
├── scripts/             # reset-dev.sh · seed.sh · smoke.sh
└── materials/           # ТЗ, брендбук (не в git)
```
