# API PirateHunter

Открытый REST API платформы — `backend /api/v1` (JWT). Спецификация —
OpenAPI (Swagger UI на `/docs` при `BACK_ENV=local/staging`, в проде
закрыт). Канонические контракты версионированы (`/api/v1`), auth-слой
готов к публичному API с ключами (roadmap в конце). Internal API
core-api (`/internal/*`) и fsp_registry (`/fsp/v1`, `/oidc/*`) наружу не
выставлены (PRD §4.2) — с ними общается только backend.

## Аутентификация

Три провайдера через интерфейс `IdentityProvider`, JWT HS256
(access короткий + refresh в httpOnly-cookie `ph_refresh`):

| Метод | Путь | Описание |
|---|---|---|
| POST | `/auth/email/request` | код на email (SMTP; без SMTP — в лог, `dev_code` при `BACK_ENV=local`). TTL 600 с, кулдаун 60 с, 5 попыток, лимиты 10/сут на адрес и 30/сут с IP |
| POST | `/auth/email/verify` | `{email, code}` → JWT-пара (роль выбирается при первом входе) |
| POST | `/auth/refresh` | refresh по cookie → новая access |
| POST | `/auth/logout` | сброс cookie |
| GET | `/auth/fsp/authorize` | вход через FSP ID: `{authorize_url}` мок-OIDC (login_hint=fsp_id) |
| GET/POST | `/auth/fsp/callback` | OIDC-callback: GET — browser (на origin фронта), POST — для API-клиентов |
| POST | `/auth/dev` | dev-login демо-аккаунтами (`candidate` / `candidate-fsp` / `employer`), только `BACK_AUTH_DEV_LOGIN=1` |
| GET | `/users/me` | профиль сессии (включая `fsp_id`) |
| POST | `/users/me/role` | выбор роли при онбординге (candidate / employer) |

Чекбоксы при регистрации: согласие на обработку ПДн (152-ФЗ) и
отдельно на публикацию профиля.

## Кандидат

| Метод | Путь | Описание |
|---|---|---|
| GET/PUT | `/candidate/profile` | профиль: ФИО, контакты, стек, специализация, заявленный грейд, роли, стаж, софт-скиллы, согласия |
| POST | `/candidate/profile/resume` | загрузка PDF → разбор в черновик профиля (текст обезличивается перед LLM; обязателен ручной review) |
| GET | `/candidate/profile/pdf` | стандартизированный PDF-профиль в гамме ФСП |
| POST/DELETE | `/candidate/fsp-link` | привязка/отвязка ФСП ID → достижения + fsp_score + снапшот (404 = нет истории → score 0) |
| GET | `/candidate/grade` | статус грейда, история тестов, кулдауны (смена грейда 90 дн, повтор теста 30 дн — даты доступности) |
| POST | `/tests/sessions` | старт CAT-теста `{grade_target, mode: full\|express}` → первая задача |
| POST | `/tests/sessions/{id}/answers` | ответ → следующая задача \| результат `{theta, se, outcome, grade_verified, breakdown}` |
| GET | `/candidate/invitations` | входящие приглашения (компания, текст, **вилка ЗП**, способ связи) |
| POST | `/candidate/invitations/{id}/accept` | принять → контакты раскрываются обеим сторонам |
| POST | `/candidate/invitations/{id}/decline` | отклонить |
| GET | `/vacancies?filters` | опубликованные вакансии (опц. фича) |
| POST | `/vacancies/{id}/apply` | отклик с сопроводительным |

## Работодатель

| Метод | Путь | Описание |
|---|---|---|
| GET/PUT | `/employer/company` | профиль компании |
| CRUD | `/employer/needs` | потребности (raw_text + структура: spec, grade, stack_must/nice, вилка) |
| POST | `/employer/needs/parse` | LLM-разбор свободного текста → «мы поняли так» (fallback — keyword) |
| GET | `/employer/needs/{id}/shortlist` | подборка: ranked кандидаты + explanation + блок «рядом с запросом» |
| GET | `/employer/market/salary?spec&grade` | виджет «вилка vs рынок»: p25/p50/p75 по данным платформы + размер категории |
| GET | `/employer/candidates?spec&grade&stack&fsp&category` | банк кандидатов с фильтрами |
| POST/GET | `/employer/invitations` | приглашения (вилка обязательна — 422 без неё; лимит 100/час на компанию), трекер статусов |
| CRUD | `/employer/vacancies` | вакансии (вилка обязательна, gross/net подписан) |
| GET | `/employer/vacancies/{id}/applications` | входящие отклики, смена статусов |

## Справочник и общее

| Метод | Путь | Описание |
|---|---|---|
| GET | `/catalog` | 7 специализаций × 4 грейда (backend кэширует ответ core, TTL 300 с) |
| GET | `/health` | healthcheck |

## Формат ошибок

Единый стиль: HTTP-код + JSON `{ "detail": "человекочитаемое описание" }`.

- **422** — валидация схемы (Pydantic, тело с деталями полей) или
  доменная валидация (нет вилки, неизвестный slug специализации);
- **401/403** — нет токена / чужой ресурс или роль не подходит
  (зависимости FastAPI: кандидат не видит чужие приглашения,
  работодатель не видит контакты до accept);
- **404** — ресурс не найден (включая «нет истории ФСП» у реестра);
- **409** — конфликт состояния: смена грейда в кулдауне, ФСП ID уже у
  другого аккаунта;
- **429** — лимиты (коды на email, приглашения);
- **502** — core-api недоступен;
- **500** — `{ "detail": "внутренняя ошибка: <Type>: <msg>" }` (глобальный
  handler, без стека наружу).

## ATS-сценарий (roadmap-концепция ТЗ)

По определению из ответов 07.10: ATS = «синхронизация вакансий,
откликов и статусов с внутренней системой найма работодателя через API,
чтобы платформа встраивалась в существующий процесс, а не требовала
ручного дублирования». Концепция (в MVP не реализуем, схема зафиксирована):

1. Работодатель заводит API-ключ в кабинете; аутентификация
   `X-API-Key` (argon2-хэш ключа, паттерн известен).
2. Синхронизация вакансий: `POST /api/v1/employer/vacancies` из ATS
   (или полный обмен по webhook-эндпоинтам ATS).
3. Статусы: webhooks платформы по смене статусов приглашений/откликов
   (`sent → viewed → accepted/declined`) + маппинг на типовые этапы
   ATS-воронки (screening → interview → offer).

**Полная проработка** — защита от недобросовестных работодателей (модель
угроз, что уже в MVP и что в roadmap) и интеграция с ATS (сценарии,
подписи вебхуков, идемпотентность, примеры) — в
[ANTIFRAUD-ATS.md](ANTIFRAUD-ATS.md).

## Roadmap API

- **Публичный API с ключами** (`/public/v1`, паттерн piratepitch):
  версионирование `/api/v1` и auth-слой уже готовы — дёшево.
- **MCP-сервер для ИИ-агентов**: инструменты «описать потребность →
  получить shortlist → отправить приглашение» поверх того же REST API.
