# core-api (hunter_core): uv-образ; compose запускает
# uv run --frozen --no-dev uvicorn app.main:app --host 0.0.0.0 --port 51457
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# слой зависимостей — по lockfile (lockfile обязан быть в sync с pyproject)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# код (engine/, itembank/, llm/, validation/, app/, cli.py)
COPY . .

EXPOSE 51457
CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "51457"]
