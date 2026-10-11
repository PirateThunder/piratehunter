# PirateHunter Frontend

Лендинг + личные кабинеты кандидата и работодателя (Next.js 16, FSD).

## Быстрый старт

```bash
bun install
bun run dev        # http://localhost:3000
```

Прод локально: `bun run build && PORT=56151 bun start`.

Качество: `bun run lint`, `bunx tsc --noEmit`.

## Окружение (см. .env.example)

- `NEXT_PUBLIC_DEV_LOGIN` — `1` показывает dev-вход демо-аккаунтами на /login.
- `NEXT_PUBLIC_API_MOCK` — `1` включает мок-фикстуры ЛК (офлайн-разработка); по умолчанию — живой backend.
- `BACKEND_URL` — куда проксируется `/api/*` (запекается при сборке).

## Docker

```bash
docker build --build-arg NEXT_PUBLIC_DEV_LOGIN=1 --build-arg BACKEND_URL=http://backend:64844 -t ph-frontend .
docker run -p 56151:56151 ph-frontend
```

Архитектура, конвенции и contract notes — в `AGENTS.md`. Контрактные типы API — `src/fsd/shared/api/types.ts` (PRD §8.1, сверены с живым OpenAPI 2026-10-08).
