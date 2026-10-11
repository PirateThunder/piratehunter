"""GET /internal/catalog — справочник специализаций/грейдов/тем (PRD §8.2)."""

from __future__ import annotations

from fastapi import APIRouter

from app.catalog.schemas import CatalogOut
from engine.catalog import catalog_dict

router = APIRouter(tags=["catalog"])


@router.get(
    "/catalog",
    response_model=CatalogOut,
    summary="Справочник специализаций, грейдов и тем (PRD §6)",
)
async def get_catalog() -> dict:
    return catalog_dict()
