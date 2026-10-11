"""Справочник специализаций/грейдов/тем — прокси к core с кэшем в
памяти (§6: справочник единый в core, backend тянет по HTTP и кэширует)."""

import time

from fastapi import APIRouter, HTTPException

from .config import get_settings
from .core_client.client import CoreDep, CoreError

router = APIRouter(tags=["catalog"])

_cache: tuple[float, dict | None] = (0.0, None)


@router.get(
    "/catalog",
    summary="Справочник специализаций и грейдов (из core)",
)
async def get_catalog(core: CoreDep) -> dict:
    global _cache
    now = time.monotonic()
    cached_at, cached = _cache
    if cached is not None and now - cached_at < get_settings().catalog_cache_ttl:
        return cached
    try:
        catalog = await core.get_catalog()
    except CoreError as e:
        if cached is not None:
            return cached  # core моргнул — отдаём протухший кэш
        raise HTTPException(502, f"core-api: {e}") from e
    _cache = (now, catalog)
    return catalog
