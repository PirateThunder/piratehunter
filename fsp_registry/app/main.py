"""FastAPI-приложение fsp_registry.

Мок-реестр достижений ФСП (GET /fsp/v1/profiles/{fsp_id}) + мок-OIDC
«FSP ID» для входа на платформу (PRD §5.3, §7.1, §8.3). Internal-сервис:
вызывается только backend'ом, наружу не выставлен (PRD §4.2). Базы нет —
вся синтетика детерминированно генерируется в памяти.

Запуск: uv run uvicorn app.main:app --host 0.0.0.0 --port 52457
"""

from fastapi import FastAPI

from . import __version__
from .config import get_settings
from .health.router import router as health_router
from .oidc.exceptions import OAuthError, oauth_error_handler
from .oidc.router import router as oidc_router
from .profiles.exceptions import ProfileNotFoundError, profile_not_found_handler
from .profiles.router import router as profiles_router

SHOW_DOCS_IN = {"local"}

app_kwargs: dict = {
    "title": "FSP Registry (mock)",
    "version": __version__,
    "description": "Мок-реестр достижений ФСП и мок-OIDC провайдер «FSP ID». "
    "Детерминированная синтетика без БД: один fsp_id → один ответ. "
    "Контракт OIDC приближен к боевому Keycloak — переезд = смена "
    "base_url и client-конфига у backend (PRD §7.1).",
}
if get_settings().env not in SHOW_DOCS_IN:
    app_kwargs["openapi_url"] = None  # /docs — только при FSPREG_ENV=local

app = FastAPI(**app_kwargs)

app.add_exception_handler(ProfileNotFoundError, profile_not_found_handler)
app.add_exception_handler(OAuthError, oauth_error_handler)

app.include_router(health_router)
app.include_router(profiles_router, prefix="/fsp/v1")
app.include_router(oidc_router)
