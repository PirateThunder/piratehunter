"""GET /health — compose-healthcheck дёргает urllib'ом, без internal-токена."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: str


@router.get("/health", response_model=HealthOut, summary="Healthcheck", include_in_schema=False)
async def health() -> HealthOut:
    return HealthOut(status="ok")
