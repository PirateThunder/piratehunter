FROM python:3.13-slim

# weasyprint (PDF-профиль §7.10): pango/cairo/gdk-pixbuf + шрифты с
# кириллицей
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
    libgdk-pixbuf-2.0-0 libcairo2 libfontconfig1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY alembic/ alembic/
COPY app/ app/

# миграции: uv run --frozen --no-dev alembic upgrade head
# сиды:       uv run --frozen --no-dev python -m app.seeds
CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "64844"]
