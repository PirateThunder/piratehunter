#!/usr/bin/env bash
# PirateHunter — сквозной смоук живого контура (docker compose up).
# Проверяет: health всех сервисов, email-код, dev-login, профиль кандидата,
# тест-движок через backend→core, потребность+shortlist, банк, приглашение
# с вилкой и раскрытие контактов после accept, полный OIDC-флоу «FSP ID».
# Запуск: ./scripts/smoke.sh  (нужны curl и jq; стек на 127.0.0.1-портах)
set -euo pipefail

FRONT=http://localhost:56151          # origin фронта (Next проксирует /api/*)
API=$FRONT/api/v1
BACK=http://localhost:64844
CORE=http://localhost:51457
FSP=http://localhost:52457

step() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
ok()   { printf '\033[32mOK\033[0m %s\n' "$*"; }
die()  { printf '\033[31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }
jqget() { jq -r "$1 // empty"; }

step "1. Health всех сервисов"
[ "$(curl -s "$BACK/health" | jqget .status)" = ok ] || die "backend health"
[ "$(curl -s "$CORE/health" | jqget .status)" = ok ] || die "core-api health"
[ "$(curl -s "$FSP/health"  | jqget .status)" = ok ] || die "fsp-registry health"
curl -sf -o /dev/null "$FRONT/"       || die "frontend /"
curl -sf -o /dev/null "$FRONT/login"  || die "frontend /login"
ok "backend, core-api, fsp-registry, frontend — живы"

step "2. Dev-login: кандидат с ФСП-историей + работодатель"
CAND_TOKEN=$(curl -sf -X POST "$API/auth/dev" -H 'content-type: application/json' \
  -d '{"account":"candidate-fsp"}' | jqget .access_token)
EMP_TOKEN=$(curl -sf -X POST "$API/auth/dev" -H 'content-type: application/json' \
  -d '{"account":"employer"}' | jqget .access_token)
[ -n "$CAND_TOKEN" ] && [ -n "$EMP_TOKEN" ] || die "dev-login"
ok "токены получены"

step "3. Email-код (dev_code при BACK_ENV=local без SMTP)"
EMAIL="smoke-$(date +%s)@demo.dev"
DEV_CODE=$(curl -sf -X POST "$API/auth/email/request" -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\"}" | jqget .dev_code)
if [ -z "$DEV_CODE" ]; then
  # prod-режим (BACK_ENV != local): dev_code не отдаётся — код пишется
  # в лог backend; смоук читает его оттуда (нужен docker-compose рядом)
  DEV_CODE=$(docker compose logs backend --since 3m 2>/dev/null \
    | grep -oP "код для \Q$EMAIL\E: \K\d+" | tail -1)
fi
[ -n "$DEV_CODE" ] || die "dev_code не вернулся и в логах не нашёлся"
MAIL_TOKEN=$(curl -sf -X POST "$API/auth/email/verify" -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"code\":\"$DEV_CODE\"}" | jqget .access_token)
[ -n "$MAIL_TOKEN" ] || die "email verify"
ok "вход по email-коду работает ($EMAIL)"

step "4. Профиль кандидата (PUT) — self: контакты видны"
curl -sf -X PUT "$API/candidate/profile" -H "authorization: Bearer $CAND_TOKEN" \
  -H 'content-type: application/json' -d '{
    "fio": "Демо Кандидатов", "spec_slug": "backend", "grade_claimed": "middle",
    "stack": ["python", "fastapi", "postgresql", "redis", "docker"],
    "phone": "+7 900 000-00-00",
    "contacts": {"email": "candidate@demo.dev", "telegram": "@demo_candidate"},
    "about": "Бэкендер, люблю тесты"}' | jq -e '.fio == "Демо Кандидатов"' > /dev/null \
  || die "PUT /candidate/profile"
ok "профиль сохранён"

step "5. Тест на грейд (backend → core-api CAT)"
SESSION=$(curl -sf -X POST "$API/tests/sessions" -H "authorization: Bearer $CAND_TOKEN" \
  -H 'content-type: application/json' -d '{"grade_target":"middle"}')
SID=$(echo "$SESSION" | jqget .session_id)
[ -n "$SID" ] || die "старт сессии: $SESSION"
QUESTION=$(echo "$SESSION" | jq -c .question)
echo "вопрос 1: $(echo "$QUESTION" | jq -r '.instance.stem // .instance.text // .type' | head -c 90)…"
RESULT=""
for i in $(seq 1 15); do
  RESP=$(curl -sf -X POST "$API/tests/sessions/$SID/answers" \
    -H "authorization: Bearer $CAND_TOKEN" -H 'content-type: application/json' \
    -d '{"answer":0}')
  RESULT=$(echo "$RESP" | jq -c '.result // empty')
  [ -n "$RESULT" ] && break
  QUESTION=$(echo "$RESP" | jq -c .next_question)
done
[ -n "$RESULT" ] || die "тест не завершился за 15 ответов"
echo "результат: $(echo "$RESULT" | jq -c '{theta, grade_verified, outcome}')"
ok "CAT-сессия завершена, грейд: $(echo "$RESULT" | jqget .grade_verified)"

step "6. Работодатель: компания + потребность"
curl -sf -X PUT "$API/employer/company" -H "authorization: Bearer $EMP_TOKEN" \
  -H 'content-type: application/json' -d '{
    "name": "Демо Корп", "industry": "IT",
    "contacts": {"hr": "hr@demo.corp"}, "site": "https://demo.corp"}' \
  | jq -e '.name == "Демо Корп"' > /dev/null || die "PUT /employer/company"
NEED=$(curl -sf -X POST "$API/employer/needs" -H "authorization: Bearer $EMP_TOKEN" \
  -H 'content-type: application/json' -d '{
    "raw_text": "Ищем backend-разработчика middle на Python/FastAPI, PG, Redis",
    "spec_slug": "backend", "grade": "middle",
    "stack_must": ["python", "fastapi", "postgresql"],
    "salary_from": 250000, "salary_to": 350000}')
NEED_ID=$(echo "$NEED" | jqget .id)
[ -n "$NEED_ID" ] || die "POST /employer/needs: $NEED"
ok "компания и потребность $NEED_ID созданы"

step "7. Shortlist с объяснением (core match)"
SHORT=$(curl -sf "$API/employer/needs/$NEED_ID/shortlist" \
  -H "authorization: Bearer $EMP_TOKEN")
echo "$SHORT" | jq -e '.results | length > 0' > /dev/null || die "shortlist пуст: $SHORT"
echo "$SHORT" | jq -e '.results[0].explanation | length > 0' > /dev/null || die "нет explanation"
# цель приглашения — наш кандидат (идемпотентно и на засеянной базе)
CAND_ID=$(curl -sf "$API/candidate/profile" -H "authorization: Bearer $CAND_TOKEN" \
  | jqget .candidate_id)
[ -n "$CAND_ID" ] || die "свой candidate_id не получен"
echo "$SHORT" | jq -c '.results[0] | {candidate_id: .candidate.profile.candidate_id, score, explanation: [.explanation[]?.human_text]}' 2>/dev/null | head -c 500; echo
ok "shortlist получен ($(echo "$SHORT" | jq '.results | length') строк), цель — наш кандидат $CAND_ID"

step "8. Банк: контакты скрыты до accept (наш кандидат в выдаче)"
CONTACTS=$(curl -sf "$API/employer/candidates?spec=backend&limit=100" \
  -H "authorization: Bearer $EMP_TOKEN" \
  | jq -c --arg id "$CAND_ID" '[.[] | select(.profile.candidate_id == $id)][0].contacts')
[ "$CONTACTS" = null ] || die "контакты утекают до accept: $CONTACTS"
ok "contacts: null — правило видимости держится"

step "9. Приглашение: без вилки 422, с вилкой 201"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/employer/invitations" \
  -H "authorization: Bearer $EMP_TOKEN" -H 'content-type: application/json' \
  -d "{\"candidate_id\":\"$CAND_ID\",\"text\":\"без вилки\",\"contact_method\":\"звонок\"}")
[ "$CODE" = 422 ] || die "без вилки ожидали 422, получили $CODE"
INV=$(curl -sf -X POST "$API/employer/invitations" \
  -H "authorization: Bearer $EMP_TOKEN" -H 'content-type: application/json' \
  -d "{\"candidate_id\":\"$CAND_ID\",\"text\":\"Приглашаем на backend middle\",
       \"salary_from\":250000,\"salary_to\":350000,\"salary_type\":\"gross\",
       \"contact_method\":\"телеграм hr\"}")
INV_ID=$(echo "$INV" | jqget .id)
[ -n "$INV_ID" ] || die "приглашение: $INV"
ok "приглашение $INV_ID отправлено (250–350 тыс gross)"

step "10. Кандидат: инбокс → accept → контакты раскрыты обеим сторонам"
INBOX=$(curl -sf "$API/candidate/invitations" -H "authorization: Bearer $CAND_TOKEN")
echo "$INBOX" | jq -e '[.[] | select(.id == "'"$INV_ID"'")][0].company.contacts == null' > /dev/null \
  || die "контакты компании видны до accept"
curl -sf -X POST "$API/candidate/invitations/$INV_ID/accept" \
  -H "authorization: Bearer $CAND_TOKEN" > /dev/null || die "accept"
AFTER=$(curl -sf "$API/candidate/invitations" -H "authorization: Bearer $CAND_TOKEN")
echo "$AFTER" | jq -e '[.[] | select(.id == "'"$INV_ID"'")][0].company.contacts.contacts.hr == "hr@demo.corp"' \
  > /dev/null || die "контакты компании не открылись кандидату после accept"
EMP_VIEW=$(curl -sf "$API/employer/invitations" -H "authorization: Bearer $EMP_TOKEN")
echo "$EMP_VIEW" | jq -e '[.. | objects | .email? // empty] | index("candidate@demo.dev")' > /dev/null \
  || die "контакты кандидата не открылись работодателю после accept"
ok "accept → обе стороны видят контакты"

step "11. Полный OIDC-флоу «FSP ID» (redirect-цепочка)"
AUTHZ=$(curl -sf "$API/auth/fsp/authorize?fsp_id=fsp_001" \
  -H "authorization: Bearer $MAIL_TOKEN" 2>/dev/null || curl -sf "$API/auth/fsp/authorize?fsp_id=fsp_001")
AUTHZ_URL=$(echo "$AUTHZ" | jqget .authorize_url)
case "$AUTHZ_URL" in
  http://localhost:52457/*|http://127.0.0.1:52457/*) ;;
  *) die "authorize_url не browser-facing: $AUTHZ_URL" ;;
esac
CODE_URL=$(curl -s -o /dev/null -w '%{redirect_url}' "$AUTHZ_URL")
[ -n "$CODE_URL" ] || die "реестр не вернул 303 (форма вместо редиректа?)"
case "$CODE_URL" in *code=*state=*) ;; *) die "в редиректе нет code+state: $CODE_URL" ;; esac
JAR=$(mktemp)
FINAL=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -c "$JAR" "$CODE_URL")
case "$FINAL" in 303*login/callback*) ;; *) die "callback не увёл на /login/callback: $FINAL" ;; esac
grep -q ph_refresh "$JAR" || die "refresh-cookie не установлена"
FSP_TOKEN=$(curl -sf -X POST "$API/auth/refresh" -b "$JAR" | jqget .access_token)
[ -n "$FSP_TOKEN" ] || die "refresh по cookie"
ME=$(curl -sf "$API/users/me" -H "authorization: Bearer $FSP_TOKEN")
[ "$(echo "$ME" | jqget .fsp_id)" = fsp_001 ] || die "users/me: $ME"
rm -f "$JAR"
ok "FSP ID: fsp_001 вошёл, refresh-cookie → access, users/me подтверждён"

step "12. LLM-парсинг потребности (backend → core /internal/llm/parse-need)"
PARSED=$(curl -sf -X POST "$API/employer/needs/parse" \
  -H "authorization: Bearer $EMP_TOKEN" -H 'content-type: application/json' \
  -d '{"raw_text":"Ищем мидла на FastAPI, PG, Redis, 250–350к, желательно Docker"}')
[ "$(echo "$PARSED" | jqget .spec)" = backend ] || die "parse spec: $PARSED"
[ "$(echo "$PARSED" | jqget .grade)" = middle ] || die "parse grade: $PARSED"
echo "$PARSED" | jq -c '{spec, grade, stack_must, stack_nice, confidence}'
ok "«мы поняли так» работает (без ключа — детерминированный fallback)"

step "13. Экспресс-режим теста для жюри (§7.4.2): ровно 4 вопроса"
SESSION=$(curl -sf -X POST "$API/tests/sessions" -H "authorization: Bearer $CAND_TOKEN" \
  -H 'content-type: application/json' -d '{"grade_target":"junior","mode":"express"}')
SID=$(echo "$SESSION" | jqget .session_id)
[ -n "$SID" ] || die "старт экспресса: $SESSION"
RESULT=""
for i in $(seq 1 6); do
  RESP=$(curl -sf -X POST "$API/tests/sessions/$SID/answers" \
    -H "authorization: Bearer $CAND_TOKEN" -H 'content-type: application/json' \
    -d '{"answer":0}')
  RESULT=$(echo "$RESP" | jq -c '.result // empty')
  [ -n "$RESULT" ] && break
done
[ -n "$RESULT" ] || die "экспресс не завершился за 6 ответов"
[ "$(echo "$RESULT" | jqget .mode)" = express ] || die "mode != express: $RESULT"
N_ASKED=$(echo "$RESULT" | jq '.asked | length')
[ "$N_ASKED" -le 4 ] || die "экспресс длиннее 4 вопросов: $N_ASKED"
ok "экспресс завершён за $N_ASKED вопроса, mode=express"

step "14. Рынок вилок (§7.5.5): медиана по данным платформы"
MKT=$(curl -sf "$API/employer/market/salary?spec=backend&grade=middle" \
  -H "authorization: Bearer $EMP_TOKEN")
[ "$(echo "$MKT" | jqget .sample_needs)" -ge 1 ] 2>/dev/null || die "market: $MKT"
echo "$MKT" | jq -e '.from_p50 == 250000 and .to_p50 == 350000' > /dev/null || die "market p50: $MKT"
echo "$MKT" | jq -c '{sample_needs, sample_invitations, from_p25, from_p50, from_p75, category_size}'
ok "медиана вилок backend×middle = 250000 (по потребностям и приглашениям)"

step "15. Вакансии: работодатель публикует — кандидат видит"
VAC=$(curl -sf -X POST "$API/employer/vacancies" -H "authorization: Bearer $EMP_TOKEN" \
  -H 'content-type: application/json' -d '{
    "title": "Backend-разработчик (FastAPI)",
    "description": "Команда платформы, сервисы на FastAPI и PostgreSQL.",
    "spec_slug": "backend", "grade": "middle",
    "stack_must": ["python","fastapi","postgresql"],
    "salary_from": 260000, "salary_to": 380000, "salary_type": "gross"}')
VAC_ID=$(echo "$VAC" | jqget .id)
[ -n "$VAC_ID" ] || die "создание вакансии: $VAC"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/vacancies/$VAC_ID/apply" \
  -H "authorization: Bearer $CAND_TOKEN" -H 'content-type: application/json' -d '{}')
[ "$CODE" = 404 ] || die "черновик не должен быть виден кандидату (ждали 404, получили $CODE)"
curl -sf -X POST "$API/employer/vacancies/$VAC_ID/publish" -H "authorization: Bearer $EMP_TOKEN" \
  | jq -e '.status == "published"' > /dev/null || die "publish"
VISIBLE=$(curl -sf "$API/vacancies?spec=backend&limit=50" -H "authorization: Bearer $CAND_TOKEN" \
  | jq -r --arg id "$VAC_ID" '[.[] | select(.id == $id)][0].title')
[ "$VISIBLE" = "Backend-разработчик (FastAPI)" ] || die "вакансия не видна кандидату: $VISIBLE"
ok "вакансия $VAC_ID опубликована и видна кандидатам"

step "16. Отклик кандидата (§7.7 — инициатива) + защита от дублей"
APP=$(curl -sf -X POST "$API/vacancies/$VAC_ID/apply" -H "authorization: Bearer $CAND_TOKEN" \
  -H 'content-type: application/json' -d '{"message":"Интересна платформа, готов обсудить"}')
APP_ID=$(echo "$APP" | jqget .id)
[ -n "$APP_ID" ] || die "отклик: $APP"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/vacancies/$VAC_ID/apply" \
  -H "authorization: Bearer $CAND_TOKEN" -H 'content-type: application/json' -d '{"message":"дубль"}')
[ "$CODE" = 409 ] || die "повторный отклик ожидали 409, получили $CODE"
ok "отклик $APP_ID создан, повтор отклонён (409)"

step "17. Работодатель видит контакты откликнувшегося → invited → кандидат видит компанию"
VIEW=$(curl -sf "$API/employer/vacancies/$VAC_ID/applications" -H "authorization: Bearer $EMP_TOKEN")
echo "$VIEW" | jq -e --arg id "$APP_ID" '[.[] | select(.id == $id)][0].candidate.contacts.contacts != null' \
  > /dev/null || die "контакты откликнувшегося не видны: $VIEW"
curl -sf -X PATCH "$API/employer/applications/$APP_ID" -H "authorization: Bearer $EMP_TOKEN" \
  -H 'content-type: application/json' -d '{"status":"invited"}' \
  | jq -e '.status == "invited"' > /dev/null || die "PATCH → invited"
curl -sf "$API/candidate/applications" -H "authorization: Bearer $CAND_TOKEN" \
  | jq -e --arg id "$APP_ID" '[.[] | select(.id == $id)][0].company.contacts.contacts != null' \
  > /dev/null || die "контакты компании не открылись приглашённому кандидату"
ok "контакты: отклик открыл их работодателю, invited — кандидату"

step "СМОУК ПРОЙДЕН"
echo "Все 17 шагов зелёные. Стек живой, сквозной сценарий работает."
