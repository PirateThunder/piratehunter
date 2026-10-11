"""GET /fsp/v1/profiles/{fsp_id} — адаптер реестра достижений (PRD §8.3).

После хакатона мок заменяется реальным реестром — backend не меняется
(PRD §7.9), поэтому контракт держим стабильным.
"""

from fastapi import APIRouter, status

from .exceptions import ProfileNotFoundError
from .schemas import FspProfile
from .service import build_profile

router = APIRouter(tags=["profiles"])


@router.get(
    "/profiles/{fsp_id}",
    response_model=FspProfile,
    status_code=status.HTTP_200_OK,
    summary="Профиль достижений ФСП по fsp_id",
    responses={404: {"description": "У пользователя нет истории ФСП"}},
)
async def get_profile(fsp_id: str) -> FspProfile:
    profile = build_profile(fsp_id)
    if profile is None:
        raise ProfileNotFoundError(fsp_id)
    return profile
