"""GET /health — healthcheck для docker compose (urllib из healthcheck'а ждёт 200)."""

from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Healthcheck",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
