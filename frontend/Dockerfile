# Dependencies stage — Bun for fast installs
FROM oven/bun:1-slim AS deps
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Build stage — Node.js 22 for the Next.js 16 build
FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Public env is inlined into the client bundle at build time — the image must
# be rebuilt when NEXT_PUBLIC_* values change. BACKEND_URL is also build-time:
# rewrites() are frozen into dist/routes-manifest.json during `next build`.
ARG NEXT_PUBLIC_DEV_LOGIN=
ARG NEXT_PUBLIC_API_MOCK=
ARG BACKEND_URL=http://localhost:64844
ENV NEXT_PUBLIC_DEV_LOGIN=$NEXT_PUBLIC_DEV_LOGIN \
    NEXT_PUBLIC_API_MOCK=$NEXT_PUBLIC_API_MOCK \
    BACKEND_URL=$BACKEND_URL
RUN npm run build

# Production stage
FROM node:22-slim AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=56151

COPY --from=builder --chown=node:node /app/dist ./dist
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/package.json ./package.json
COPY --from=builder --chown=node:node /app/next.config.ts ./next.config.ts
COPY --from=builder --chown=node:node /app/public ./public

USER node

EXPOSE 56151

CMD ["node", "node_modules/next/dist/bin/next", "start"]
