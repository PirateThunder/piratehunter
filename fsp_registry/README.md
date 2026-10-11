# fsp_registry — мок-реестр достижений ФСП + мок-OIDC «FSP ID»

Internal-сервис (PRD §5.3, §8.3): вызывается только backend'ом, наружу не
выставлен. Базы нет — вся синтетика детерминированно генерируется в памяти:
один `fsp_id` → всегда один ответ (seed = sha256 от соли и fsp_id).
После хакатона мок заменяется реальным реестром/Keycloak — backend не
меняется, только base_url и client-конфиг (PRD §7.9).

## Запуск

```bash
uv sync                      # зависимости
uv run uvicorn app.main:app --port 52457
uv run pytest -q             # тесты
uv run ruff check app tests
```

В compose: `docker compose up -d fsp-registry` (порт 52457, healthcheck —
`GET /health` → `{"status":"ok"}`).

## Реестр достижений

`GET /fsp/v1/profiles/{fsp_id}` → `200 FspProfile` | `404 {"detail": ...}`

~60% fsp_id имеют историю, ~40% — 404 («пользователь без истории ФСП»,
обязательный кейс ТЗ, PRD §7.9). Все даты строго в прошлом относительно
2026-10; затухание свежести считает core (PRD §7.5.2).

```json
{
  "fsp_id": "fsp_001",
  "rating": 1623,
  "ranks": [{"discipline": "хакатон", "rank": "кандидат в мастера спорта", "date": "2022-04-13"}],
  "contests": [{
    "name": "Чемпионат по робототехнике 2023",
    "discipline": "робототехника",
    "date": "2024-07-31",
    "place": 2,
    "diploma": 2,
    "team": true,
    "team_result": {"team_name": "Красная сложность", "place": 2}
  }],
  "events": [{"name": "Чемпионат ФСП 2021", "date": "2025-06-05", "role": "спикер"}]
}
```

`diploma`: `1|2|3|null` (диплом I–III степени = места 1–3); `team_result`
есть iff `team: true`. Поля `level` у соревнований нет — дисциплины и
уровни не ранжируем (PRD §7.9, Q&A 06.10).

## Мок-OIDC «FSP ID» (вход на платформу)

Стандартный authorization-code flow:

1. Backend редиректит браузер на
   `GET /oidc/authorize?client_id=...&redirect_uri=...&response_type=code&scope=openid&state=...`
   — с `login_hint=fsp_NNN` код выдаётся сразу (вход одним кликом),
   без него показывается HTML-форма выбора из 20 синтетических
   пользователей (`fsp_001`…`fsp_020`; `fsp_001` — демо с богатой
   историей). Ответ — `303 redirect_uri?code=...&state=...`.
2. Backend меняет код (server-to-server):
   `POST /oidc/token` (form: `grant_type=authorization_code`, `code`,
   `redirect_uri`, `client_id`) → `{access_token, id_token, token_type,
   expires_in}`. Код одноразовый, TTL 300 c.
3. `GET /oidc/userinfo` с `Authorization: Bearer <access_token>` →
   `{sub, name, email, email_verified}`. `sub` = `fsp_id`.

Токены — JWT HS256 на локальном секрете. Claims id_token: `iss, sub,
aud, iat, exp, name, email`. Ошибки — OAuth-формат
`{"error", "error_description"}` (invalid_client / invalid_grant /
invalid_token). Discovery: `GET /.well-known/openid-configuration`.

Из 20 личностей 14 с историей ФСП, 6 с 404-профилем (для демо-кейса
«нет истории»): `fsp_003, fsp_008, fsp_009, fsp_010, fsp_011, fsp_015`.

## Настройки (env, префикс FSPREG_)

| Переменная | Дефолт | Назначение |
|---|---|---|
| `FSPREG_ENV` | `local` | `/docs` виден только при `local` |
| `FSPREG_JWT_SECRET` | dev-строка | подпись HS256 токенов |
| `FSPREG_ISSUER` | `http://localhost:52457` | `iss` в токенах и discovery |
| `FSPREG_OIDC_CLIENT_ID` | `piratehunter-backend` | единственный зарегистрированный клиент |
| `FSPREG_OIDC_ALLOWED_REDIRECT_URIS` | пусто | csv allowlist redirect_uri (пусто = не проверяем) |
| `FSPREG_CODE_TTL_SECONDS` | `300` | TTL authorization code |
| `FSPREG_TOKEN_TTL_SECONDS` | `3600` | TTL access/id токенов |

Compose сервис env не передаёт — дефолтов достаточно (мок, внутр. сеть).
Для стенда имеет смысл задать `FSPREG_ISSUER=http://fsp-registry:52457`.
