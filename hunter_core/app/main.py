"""FastAPI-приложение core-api (PRD §8.2).

Запуск: uv run --frozen --no-dev uvicorn app.main:app --host 0.0.0.0 --port 51457
Internal-сервис: CORS не нужен (внутренняя сеть), доступ — по X-Internal-Token
(если CORE_INTERNAL_TOKEN задан). OpenAPI/docs — только при CORE_ENV=local.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.bank import build_startup_bank
from app.catalog.router import router as catalog_router
from app.config import get_settings
from app.constants import API_TITLE, API_VERSION, INTERNAL_PREFIX
from app.database import Base, make_engine, make_session_factory
from app.dependencies import verify_internal_token
from app.exceptions import AppError
from app.health.router import router as health_router
from app.llm_parse.router import router as llm_parse_router
from app.matching.router import router as matching_router
from app.models import ItemTemplateModel
from app.resume_parse.router import router as resume_parse_router
from app.sessions.router import router as sessions_router
from app.snapshots.router import router as snapshots_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    # Alembic для core не поднимаем (в compose нет migrate-шага для core-api) —
    # осознанное упрощение хакатона: таблицы создаются на старте.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.db_engine = engine
    app.state.session_factory = make_session_factory(engine)
    # sync-сборка банка (exec/sqlite в фабриках) — вне event loop
    app.state.bank = await run_in_threadpool(build_startup_bank, settings)
    # версионный слой банка в БД (§5.2): merge идемпотентен при рестартах
    async with app.state.session_factory() as db:
        for t in app.state.bank.filter(active_only=False):
            await db.merge(
                ItemTemplateModel(
                    id=t.id, spec_slug=t.spec, topic=t.topic, grade_band=t.grade_band,
                    type=t.kind, beta=t.beta,
                    payload={"factory_id": t.factory_id, "params": t.params},
                    version=t.version, active=t.active,
                )
            )
        await db.commit()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    is_local = settings.env == "local"
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        docs_url="/docs" if is_local else None,
        openapi_url="/openapi.json" if is_local else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(health_router)
    guarded = [Depends(verify_internal_token)]
    app.include_router(catalog_router, prefix=INTERNAL_PREFIX, dependencies=guarded)
    app.include_router(sessions_router, prefix=INTERNAL_PREFIX, dependencies=guarded)
    app.include_router(snapshots_router, prefix=INTERNAL_PREFIX, dependencies=guarded)
    app.include_router(matching_router, prefix=INTERNAL_PREFIX, dependencies=guarded)
    app.include_router(llm_parse_router, prefix=INTERNAL_PREFIX, dependencies=guarded)
    app.include_router(resume_parse_router, prefix=INTERNAL_PREFIX, dependencies=guarded)
    return app


app = create_app()
