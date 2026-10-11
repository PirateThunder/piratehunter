# Agent Guide — PirateHunter Frontend

Web frontend for PirateHunter: an IT-job platform with reversed mechanics —
the employer finds candidates in a categorized base (spec × test-verified
grade) and sends an invitation with a mandatory salary range; candidate
contacts stay hidden until accept.
Stack: Next.js 16 (App Router, `reactCompiler: true`), React 19, Bun,
Tailwind v4 (CSS config), Base UI (shadcn pattern), zustand, ky,
framer-motion, Biome. Build output: `./dist` (`distDir`), container port **56151**.

## Commands

- `bun run dev` / `bun run build` / `bun start` — dev on :3000, prod on $PORT
- `bun run lint` (biome check), `bunx tsc --noEmit`

## Conventions

- FSD: `src/app` is thin routing only; everything else in `src/fsd/{app,pages,widgets,features,entities,shared}`. Alias `@/*` → `./src/*`.
- There is NO `src/app/layout.tsx` — three root layouts share `fsd/app/root-shell.tsx` (fonts via self-hosted @font-face, Providers): `(landing)` (marketing + legal stubs), `login` (bare), `(app)` (AuthGate + AppChrome; holds `/candidate*` and `/employer*`).
- Biome: 2 spaces, single quotes, semicolons asNeeded, width 100; kebab-case files; PascalCase named exports (default only for Next pages/layouts); `cn()` from `@/fsd/shared/lib/utils`; `'use client'` for interactive components.
- Forms: label↔control association via `shared/ui/field.tsx` (`Field` + useId) — bare `<label>` wrapping a custom component fails `noLabelWithoutControl`.
- Number inputs with a `step`: `min` must be 0 (step counts from min; `min=1 step=5000` rejects 250000).
- UI copy is Russian, hardcoded inline (ru-only product, no i18n layer — deliberate, same as piratepitch).
- Code comments in English.

## Theme (swappable)

- Design tokens live in ONE file: `fsd/app/styles/tokens.fsp.css` — ФСП brand
  values (PRD §3.3: accent #402FFF, ink #1B1C21/#2D2E37, bg #FFFFFF/#EDEDED,
  danger #EC1D35, radii 6/12/100px). `:root` raw `--fsp-*` + shadcn-pattern
  semantic aliases + `@theme inline` bindings. Rebrand = replace this file.
- Fonts are self-hosted in `public/fonts` (Inter variable latin+cyrillic,
  JetBrains Mono 400–700) via `@font-face` in `fsd/app/styles/fonts.css` —
  offline builds cannot fail on font downloads. Light theme only.
- Brand SVGs: `public/brand/`. NB: in the брендбук the «w» suffix means "for
  WHITE background" — on our light theme `Logo` uses `logo_01w.svg`.

## Auth / API

- Sign-in: FSP ID (`GET auth/fsp/authorize` → redirect the browser to the
  returned `authorize_url`; backend lands back on `/login/callback` with the
  refresh cookie set) or email code (`auth/email/request` →
  `auth/email/verify`); role is persisted via `POST /users/me/role`
  `{role, consent_pd: true, consent_publish}` on first login
  (`features/auth/role-select.tsx`). Dev demo-account login only when
  `NEXT_PUBLIC_DEV_LOGIN=1`.
- Access token lives in memory only (zustand `entities/session/model/session-store`);
  refresh is the httpOnly `ph_refresh` cookie (Path=/api/v1/auth) via
  `POST /auth/refresh` on app entry (`features/auth/session-bootstrap`),
  401s trigger single-flight refresh + one forced retry in `shared/api/http.ts`.
  NB (differs from piratepitch): error unwrap re-throws an HTTPError from
  afterResponse — in ky@2.1 beforeError sees an already-consumed body, and
  hook-thrown plain Errors get wrapped into a generic network error when a
  retry limit is set.
- The browser only ever talks to same-origin `/api/*`; `next.config.ts`
  rewrites proxy it to `${BACKEND_URL}` (baked at build time — Docker ARG).
- Cabinet reads go through `shared/api/cabinet-api.ts` (facade; mock fixtures
  in `shared/api/mock/` behind `NEXT_PUBLIC_API_MOCK=1`, default is live).
  Mutations and auth are always live (`features/*` → `entities/*/api`).
- Contract types — `shared/api/types.ts`; catalog (`GET /catalog`, public) is
  the source of spec/grade titles at runtime (`shared/lib/format` fallbacks).
- Authorized file downloads (`GET /candidate/profile/pdf`) go through
  `shared/lib/download.ts#downloadBlob` — blob via the ky instance (Bearer
  header), saved via a temporary object URL; plain links can't authorize.

## Routes

- `/` landing; `/privacy`, `/terms` stubs; `/login` + `/login/callback`.
- `/candidate` (tabs: Профиль / Категория и грейд / Приглашения / Настройки),
  `/candidate/test` — adaptive test flow (setup → question → result).
- `/employer` dashboard (needs + invitation tracker + company),
  `/employer/needs/new`, `/employer/needs/[id]` (editor + shortlist),
  `/employer/bank` (URL-state filters).

## Contract notes (verified against live OpenAPI 2026-10-08)

- `POST /auth/*` return `{user{id,email,fsp_id,role,is_verified}, access_token,
  expires_in}`; refresh returns `{access_token, expires_in}`.
- `POST /auth/dev` body is `{account}`: 'candidate' | 'candidate-fsp' | 'employer'.
- `GET /candidate/grade` (GradeInfo) is flat: `retest_available_at`,
  `change_available_at`, `category_rank/size`; NO test history — history is a
  phase-3 backend add-on.
- Invitations nest the counterparty: candidate view `company: {company,
  contacts|null}`, employer view `candidate: {profile, contacts|null}`;
  contacts are null until accept. Accept returns `{invitation}` with contacts
  of BOTH sides.
- Shortlist: `{need_id, results[]}`; explanation factors are
  `{factor, weight, value, contribution, human_text}` (render human_text,
  bar = contribution). `in_category` («рядом с запросом») is absent in the
  current deploy — treat missing as true.
- Tests: `POST /tests/sessions {grade_target}` → `{session_id, question}`;
  question `{template_id, topic, type: mcq|sql, time_limit, instance{
  question_text, payload, beta}}`; mcq payload `{code, options[]}` (answer =
  0-based index), sql payload `{setup_sql, schema, columns[]}` (answer =
  query string). Answers → `{next_question|null, result|null}`; result is the
  core ResultOut (`theta, se, outcome, grade_verified, grade_assigned, mode,
  breakdown{topic:{asked,correct}}`, …).
- `mode: "express"` is silently IGNORED by the current backend deploy (always
  10 questions, result.mode "full") — the UI sends it and reads the truth
  from result.mode; remove the caveat once backend honours it.
- `POST /employer/needs/parse` and `GET /employer/market/salary` are in the
  phase-2 contract but NOT yet deployed (405/404 on 2026-10-08): the UI
  degrades gracefully (parse → toast + manual editing; market → honest
  «данных пока мало»).
- Resume (§7.10, LIVE since 2026-10-08): `POST /candidate/profile/resume`
  (multipart PDF) → `{draft{spec, grade_claimed, stack[], roles[],
  experience_years, about, confidence, notes}}`; the profile is NOT changed
  server-side — the draft only prefills the form, UI enforces the mandatory
  review («проверьте перед сохранением»). 200 with empty draft + notes =
  parsing temporarily unavailable (LLM fallback); 422 = broken/not-a-PDF
  with readable detail (unwrapped by http.ts). `GET /candidate/profile/pdf`
  → application/pdf, downloaded as blob (`fetchProfilePdf` + `downloadBlob`).
- Candidate bank pager: `GET /employer/candidates` accepts `limit`/`offset`;
  UI pages by 24 with offset in URL-state, any filter change resets offset.
  The API returns a bare array (no total) — «Вперёд» keys off page size.
- No `/vacancies*` endpoints yet (PRD §7.7, optional) — phase 3.
