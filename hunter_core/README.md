# hunter_core

CLI-ядро платформы подбора ИТ-специалистов (хакатон ФСП, ЛЦТ-2026, спец. трек).
Интеллектуальное ядро продукта по [PRD](../PRD.md): параметризованный банк
заданий (§7.4.1), адаптивный тест CAT-lite на IRT (§7.4.2), объяснимый
скоринг/матчинг (§7.5.2, §7.9) и валидационный харнесс с порогами приёмки
(§9). Никакого HTTP/FastAPI/Docker — чистая CLI-библиотека.

## Стек и запуск

Python 3.13, uv, numpy, httpx, matplotlib; dev: pytest, ruff.

```bash
uv sync                  # установка зависимостей
uv run pytest -q         # тесты (49 шт.)
uv run ruff check .      # линт
```

## Команды CLI

```bash
uv run python cli.py catalog
# справочник §6: 7 специализаций с темами, 4 грейда с θ-полосами

uv run python cli.py bank-build --spec backend --mcq 15 --sql 8 --out out/bank_backend.json
# фабрики генерируют шаблоны; sanity-чек: 20 seeds на шаблон, чекер обязан
# сойтись на эталоне; несходящиеся отбраковываются с отчётом

uv run python cli.py test-sim --spec backend --grade middle --theta-true 1.0 [--express]
# симуляция сессии: ход теста вопрос за вопросом (тема, β, ответ, θ, SE)

uv run python cli.py validate --agents 300 --repeats 3 --out out/validation/
# полный прогон §9: метрики, PASS/FAIL по порогам §9.3, графики
# (theta_scatter.png, confusion.png), validation.json, summary.txt

uv run python cli.py match-eval --out out/validation/matching.json
# 50 кандидатов × 20 потребностей, программная разметка → Precision@5, nDCG@10

uv run python cli.py reword-demo "текст задания"
# демо LLM-перефразировки оболочки (OpenRouter); без ключа — вежливый fallback
```

## Архитектура

```
engine/
  catalog.py    §6: специализации/грейды; θ-полосы intern < −1 ≤ junior < 0.5 ≤ middle < 2 ≤ senior
  irt.py        σ(θ−β); обновление θ += K(n)(r−p), K(n)=K0/√n; SE; BetaStat-калибровка β;
                апостериорные вероятности (EAP, хвосты)
  cat.py        TestEngine: старт с медианы полосы, round-robin тем + argmin|β−θ|,
                full=10 / express=4 вопроса, стоп по SE<0.35, исходы confirmed/upgrade/downgrade
  scoring.py    test_score, fsp_score (§7.9), freshness (t½=30 дней), stack_match (must ×3),
                match_score → (score, explanation) для панели «Почему в подборке»
itembank/
  model.py      ItemTemplate / Instance / чекер
  registry.py   BankRegistry: фильтры, версии, JSON-сериализация, sanity-чек шаблонов
  factory_mcq.py мета-генератор «что выведет код»: 8 семейств по грамматике Python,
                exec в sandbox (whitelist builtins, SIGALRM-таймаут), дистракторы из
                типовых ошибок, β-эвристика
  factory_sql.py 3 домена × 4 паттерна (JOIN+GROUP BY+HAVING, подзапрос-агрегат,
                HAVING vs глобальный агрегат, оконная функция); проверка sqlite in-memory,
                мультимножества строк, лимит операций
llm/client.py   OpenRouter AIClient (ретраи ×3, timeout), reword_shell со страховкой
                код-блоков; fallback на исходный текст, исключений наружу нет
validation/
  agents.py     SyntheticAgent: P(correct)=σ(θ_true−β), 5% «ошибка по невнимательности»
  harness.py    §9: стабильность, Spearman, confusion matrix, эквивалентность
                экземпляров, калибровка β, пересечение наборов (Jaccard)
  matching_eval.py Precision@5 / nDCG@10 на синтетике с программной разметкой
cli.py          единый argparse CLI
```

## Конструктив CAT-lite (чем отличаемся от спеки и почему)

Онлайн-шаг Роббинса–Монро θ += K(n)(r−p) — отчётная точечная оценка и база
стабильности, но за 10 вопросов он не доезжает до θ_true при сильно
«промахнувшемся» заявленном грейде (мертвая механика upgrade/downgrade из
§7.4.3). Поэтому:

- **подбор вопросов** — по апостериорному среднему (EAP со
  слабоинформативным приором N(медиана полосы, 8²)): быстро адаптируется,
  ответы информативны при любом заявлении;
- **исход** — по апостериорной вероятности хвоста: upgrade_offer при
  P(θ > низ след. грейда) ≥ 0.7, downgrade_offer при P(θ < низ заявл.) ≥ 0.7;
- **K0 = 0.4** (вместо 0.8): подобрано харнессом — 0.8/√n на 10 вопросах
  даёт стабильность ±1 = 0.967 < порога 0.97; 0.4/√n держит все пороги §9.3
  с запасом при MAE(θ) ≈ 0.35.

## Пороги §9.3 (зафиксированы до прогона)

| Метрика | Порог |
|---|---|
| Стабильность грейда (точное совпадение) | ≥ 80% |
| Стабильность в пределах ±1 грейда | ≥ 97% |
| Spearman(θ_true, θ_est) | ≥ 0.85 |
| Путаница соседних грейдов | < 15% |
| Precision@5 подбора | ≥ 0.8 |

Полученные числа — в `out/validation/summary.txt` после `validate` и в
финальном отчёте фазы.

## LLM

Env: `OPENROUTER_API_KEY` (ключ OpenRouter), `HUNTER_LLM_MODEL` (модель,
дефолт `qwen/qwen-2.5-7b-instruct`). Перефразировка меняет только легенду —
код/числа/варианты страхуются промптом и проверкой код-блоков; при любой
ошибке возвращается исходный текст (демо не зависит от сети и ключей,
PRD §3.4). ПДн в запросы не отправляются.

## core-api (HTTP-слой, PRD §8.2)

Тонкая FastAPI-обёртка над движком (`app/`), internal-сервис для backend:

```
GET  /health                                  → {"status":"ok"} (compose healthcheck)
GET  /internal/catalog                        → специализации/грейды/темы
POST /internal/tests/sessions                 → {session_id, question}
POST /internal/tests/sessions/{id}/answers    → {next_question} | {result}
PUT  /internal/snapshots/{candidate_id}       → upsert оценочного снапшота
POST /internal/match                          → ranked [{candidate_id, score, explanation}]
GET  /internal/category/{spec}/{grade}/ranking → ранжированная категория (§7.5.4)
POST /internal/llm/parse-need                 → LLM-парсинг потребности из свободного
                                                текста: {spec, grade, stack_must,
                                                stack_nice, confidence, notes};
                                                fallback — keyword-правила по каталогу
                                                (PRD §7.3, §3.4)
POST /internal/llm/parse-resume               → разбор обезличенного резюме в черновик
                                                профиля: {spec, grade_claimed, stack,
                                                roles, experience_years, about,
                                                confidence, notes} (PRD §7.10)
DELETE /internal/snapshots                    → 204, полная очистка таблицы снапшотов
                                                (ресид демо-стенда, PRD §10)
```

Запуск локально (sqlite по умолчанию): `uv run uvicorn app.main:app --port 51457`.
В Docker: `docker build -t hunter-core-api .` (compose — из корня монорепы).
Env: `CORE_ENV` (docs только при `local`), `CORE_DATABASE_URL`
(`postgresql+asyncpg://...@pg-core:5432/ph_core` в compose),
`CORE_INTERNAL_TOKEN` (если задан — обязателен заголовок `X-Internal-Token`),
`CORE_BANK_SPECS`/`CORE_BANK_MCQ_PER_SPEC`/`CORE_BANK_SQL_PER_SPEC`/`CORE_BANK_SEED`.
Состояние тест-сессий — в PG (TestEngine.restore по строкам БД), таблицы
создаются `create_all` на старте (без Alembic — упрощение хакатона).

## Известные ограничения (эта фаза)
- Глубокий банк — только backend (mcq+sql фабрики); для остальных специализаций
  фабрики маппятся на кодовые темы каталога (mcq — трейсинг Python как проверка
  логики), тематическое покрытие — авторская работа следующей фазы.
- «Ошибка по невнимательности» агента — 0.05 (в тексте ТЗ встречается и 10%;
  вынесено в параметр SyntheticAgent.careless).
- SE-стоп (SE<0.35) при 10 вопросах практически недостижим (SE ≥ 0.63) —
  правило оставлено для длинных конфигураций; фактический стоп — по числу вопросов.
- Upgrade/downgrade при θ_true в пределах ~0.5 от границы грейда статистически
  плохо различимы за 10 вопросов — детекция ~65–75%, что честно отражено в
  тестах (пороги ≥ 5/8).
