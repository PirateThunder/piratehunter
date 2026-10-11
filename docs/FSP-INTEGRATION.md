# Интеграция с ФСП (мок-реестр + мок-OIDC «FSP ID»)

Сервис `fsp_registry` играет двойную роль (Q&A 06.10): **мок-реестр
достижений участника ФСП** (контракт `GET /fsp/v1/profiles/{fsp_id}`)
и **мок-провайдер входа «FSP ID»** (имитация OAuth/OIDC-флоу). После
хакатона мок заменяется боевым реестром/Keycloak — backend не меняется,
меняется только конфиг. Это «схема предполагаемой интеграции» из ТЗ
§3.4, исполненная в коде.

## Контракт реестра достижений

```
GET /fsp/v1/profiles/{fsp_id}
→ 200 {fsp_id, rating, ranks[{discipline, rank, date}],
       contests[{name, discipline, date, place, diploma 1|2|3|null,
                 team, team_result{team_name, place}}],
       events[{name, date, role}]}
→ 404 — истории ФСП нет
```

**Детерминированный генератор** (`fsp_registry/app/profiles/service.py`):
seed = `sha256(соль + fsp_id)` — один и тот же `fsp_id` всегда даёт один
и тот же профиль, в том числе между перезапусками. По хэшу **~60%
fsp_id имеют историю, ~40% → 404** (пользователь без истории —
обязательный кейс ТЗ). Распределение результатов: ~20% победители с
дипломом I–III, ~25% призовые места 4–10, остальные участники; ~35%
командных; рейтинг, разряды (0–3 дисциплины), мероприятия (0–4).
Поле `level` (regional/national) сознательно не заводим — эксперты
против ранжирования дисциплин и уровней (§7.9). Сервис stateless, БД
не нужна. ПДн не хранит — «человекочитаемость» обеспечивает backend
(у себя маппинг `fsp_id → candidate_id`).

## Мок-OIDC flow входа «FSP ID»

Контракт приближен к OIDC, чтобы переезд на боевой Keycloak был
конфигом. Эндпоинты fsp_registry:

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/oidc/authorize?client_id&redirect_uri&state&login_hint` | авторизация: автовыбор демо-личности или явный `fsp_id`; 303 на redirect_uri с `code+state` |
| POST | `/oidc/token` (form) | обмен кода: `{access_token, id_token, expires_in}` — self-contained JWT HS256 |
| GET | `/oidc/userinfo` (Bearer) | `{sub=fsp_id, name, email}` |
| GET | `/.well-known/openid-configuration` | discovery (issuer = browser-facing адрес) |

Коды одноразовые, in-memory с TTL; `client_id` валидируется,
`redirect_uri` — по allowlist; обмен привязан к паре code+redirect_uri
+client_id (повторный обмен → `invalid_grant`).

### Redirect-цепочка (как это проходит в браузере)

1. Фронт: `GET /api/v1/auth/fsp/authorize?fsp_id=…` → backend отдаёт
   `{authorize_url}` — browser-facing адрес реестра
   (`BACK_FSP_PUBLIC_URL`), OIDC-параметрами (`client_id`,
   `redirect_uri`, `state`, `login_hint` = fsp_id).
2. Браузер идёт на `/oidc/authorize` → реестр **303**-ит на
   `BACK_FSP_REDIRECT_URI` = **GET-callback backend'а на origin фронта**
   (`https://piratehunter.fun/api/v1/auth/fsp/callback?code&state`) —
   Next проксирует `/api/*`, поэтому refresh-cookie `ph_refresh`
   ставится на домен фронта.
3. Backend валидирует одноразовый state (Redis, TTL 600 с), обменивает
   `code → token → userinfo` у реестра, создаёт/находит User по
   `fsp_id`, подтягивает достижения, **303**-ит браузер на
   `/login/callback`.
4. Сессия поднимается bootstrap-ом: `/api/v1/auth/refresh` по
   `ph_refresh`-cookie → access в память (zustand), single-flight
   refresh в ky.
5. POST-вариант callback (code+state в теле) оставлен для API-клиентов.

Сквозной флоу покрыт смоуком (шаг 11): authorize_url → 303 (code+state)
→ callback → 303 `/login/callback` → cookie → refresh → `users/me` с
`fsp_id=fsp_001`.

## Кейс «404 = нет истории ФСП» (обязательный по ТЗ)

- Привязка ФСП ID (автоматически при входе через FSP ID или вручную в
  настройках): `fsp_registry` вернул 404 → `fsp_score = 0`, блок
  достижений **не рендерится**, UI подсказывает «привяжите ФСП ID».
- Кандидат **полностью не скрывается**: показывается со статусом,
  участвует в подборке с unverified-потолком test_score (0.4), если
  грейд подтверждён — в категории на общих основаниях.
- Фильтр работодателя «есть достижения ФСП» корректно исключает таких
  кандидатов.
- Путь покрыт тестами backend (FSP-привязка с 404, «404 = нет истории →
  score 0, блок отсутствует»); ручная демонстрация — демо-аккаунт
  `candidate` (без ФСП) против `candidate-fsp` (fsp_001 — богатая
  история). Достижения кэшируются в Redis (TTL 3600 с).

## Критерии влияния достижений (Q&A 06.10 / 07.10)

- Достижения ФСП — **буст внутри грейда** (фактор fsp_score, вес 0.20),
  на грейд не влияют: грейд присваивается только тестом.
- Дисциплины равны, уровни соревнований не ранжируются.
- Антифарм: затухание повторных явок `×0.5^(i−1)`; cap 1.0.
- Командный результат — как обычное достижение; давность не штрафуем.
- Формула и веса — в MATCHING.md; бонус за релевантность дисциплины
  специализации — опционально post-MVP (модель `discipline` заложена).

## Замена мока на боевой Keycloak — конфигом

Backend ходит к провайдеру через интерфейс `IdentityProvider`
(провайдеры `fsp-id` и `email-code`); клиент мок-OIDC параметризован:

```
BACK_FSP_PUBLIC_URL=https://fsp-id.piratehunter.fun   # issuer/authorize
BACK_FSP_REGISTRY_URL=http://fsp-registry:52457       # внутри сети
BACK_FSP_REDIRECT_URI=https://piratehunter.fun/api/v1/auth/fsp/callback
BACK_FSP_CLIENT_ID / BACK_FSP_CLIENT_SECRET           # client-конфиг
```

Переезд: поднять Keycloak с realm ФСП, завести client
(`piratehunter-backend`), поменять три env — код backend'а не трогаем
(claims mapping: `sub → fsp_id`, standard OIDC). Реестр достижений
заменяется боевым API с тем же контрактом ответа (200/404).
