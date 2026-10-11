"""Кабинетные ручки «me»: профиль текущего юзера и онбординг роли."""

from fastapi import APIRouter

from ..auth.dependencies import CurrentUser
from ..database import DbDep
from . import service
from .schemas import RoleSelectIn, UserMeOut

router = APIRouter(tags=["users"])


@router.get(
    "/users/me",
    response_model=UserMeOut,
    summary="Текущий пользователь",
)
async def get_me(user: CurrentUser) -> UserMeOut:
    """Профиль текущего юзера. role=None — нужен онбординг (выбор роли)."""
    return UserMeOut.model_validate(user)


@router.post(
    "/users/me/role",
    response_model=UserMeOut,
    summary="Выбрать роль при первом онбординге",
)
async def select_role(
    body: RoleSelectIn, user: CurrentUser, session: DbDep
) -> UserMeOut:
    """Роль candidate|employer выбирается один раз (§7.1); повтор — 409.
    consent_pd обязателен (152-ФЗ), consent_publish — отдельный чекбокс."""
    await service.select_role(
        session, user, body.role, body.consent_pd, body.consent_publish
    )
    return UserMeOut.model_validate(user)
