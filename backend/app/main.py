"""FastAPI-приложение PirateHunter Backend — публичный API платформы
(/api/v1), владелец ПДн (PRD §4.2).

Запуск: uv run uvicorn app.main:app --host 0.0.0.0 --port 64844
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router
from .candidates import bank as candidates_bank
from .candidates import router as candidates_router
from .catalog import router as catalog_router
from .companies import router as companies_router
from .config import get_settings
from .exceptions import register_exception_handlers
from .invitations import router as invitations_router
from .market import router as market_router
from .needs import router as needs_router
from .resume import router as resume_router
from .testing import router as testing_router
from .users import router as users_router
from .version import VERSION

SHOW_DOCS_IN = {"local"}

app_kwargs: dict = {
    "title": "PirateHunter Backend",
    "version": VERSION,
    "description": "Публичный API платформы-агрегатора ИТ-вакансий с "
    "обратной механикой: auth (email-код, FSP ID, dev-login), профили "
    "кандидатов и компаний, потребности, приглашения с обязательной "
    "вилкой ЗП и правилами видимости контактов (§7.6). Тест-движок и "
    "матчинг — в core-api (internal), backend оркестрирует и владеет ПДн.",
    # публичная документация API — осознанное решение для интеграторов
    # (ATS/партнёры): открывается флагом BACK_DOCS_PUBLIC=1
    "contact": {"name": "PirateHunter", "url": "https://piratehunter.fun"},
}
if get_settings().env not in SHOW_DOCS_IN and not get_settings().docs_public:
    app_kwargs["openapi_url"] = None  # /docs при BACK_ENV=local или флаге

app = FastAPI(**app_kwargs)

# фронт ходит cross-origin в dev; cookie (refresh) требует
# allow_credentials — список Origin'ов из BACK_CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", include_in_schema=False)
async def health() -> dict:
    return {"status": "ok"}


register_exception_handlers(app)

app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(users_router.router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(candidates_router.router, prefix="/api/v1")
app.include_router(resume_router.router, prefix="/api/v1")
app.include_router(candidates_bank.router, prefix="/api/v1")
app.include_router(companies_router.router, prefix="/api/v1")
app.include_router(needs_router.router, prefix="/api/v1")
app.include_router(invitations_router.router, prefix="/api/v1")
app.include_router(testing_router.router, prefix="/api/v1")
app.include_router(market_router.router, prefix="/api/v1")
