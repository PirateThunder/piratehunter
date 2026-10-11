"""Зависимости авторизации: current_user (Bearer JWT) и ролевые гарды.

Разграничение ролей — на уровне зависимостей FastAPI (ТЗ §3.5, PRD
§7.1): /candidate/* — require_candidate, /employer/* — require_employer.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..database import DbDep
from ..users.constants import ROLE_CANDIDATE, ROLE_EMPLOYER
from ..users.models import User
from . import tokens

_bearer = HTTPBearer(auto_error=False)


async def current_user(
    session: DbDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer)
    ] = None,
) -> User:
    """Юзер по Bearer access-токену (401 нет/протух, 403 banned)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "нужен Bearer access-токен (POST /auth/*)")
    try:
        user_id = tokens.verify(credentials.credentials, tokens.TYPE_ACCESS)
    except tokens.TokenError:
        raise HTTPException(
            401, "access-токен невалиден или истёк — обновите (/auth/refresh)"
        ) from None
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(401, "пользователь токена не найден")
    if user.is_banned:
        raise HTTPException(403, "пользователь заблокирован")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def optional_user(
    session: DbDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer)
    ] = None,
) -> User | None:
    """Юзер, если передан валидный Bearer; без токена — None (не 401).
    Для ручек «войти или привязать к текущему аккаунту» (email-код)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        user_id = tokens.verify(credentials.credentials, tokens.TYPE_ACCESS)
    except tokens.TokenError:
        return None
    user = await session.get(User, user_id)
    if user is None or user.is_banned:
        return None
    return user


OptionalUser = Annotated[User | None, Depends(optional_user)]


async def require_candidate(user: CurrentUser) -> User:
    """Только кандидат (role выбрана = candidate; иначе 403)."""
    if user.role != ROLE_CANDIDATE:
        raise HTTPException(403, "доступно только кандидатам")
    return user


async def require_employer(user: CurrentUser) -> User:
    """Только работодатель (role выбрана = employer; иначе 403)."""
    if user.role != ROLE_EMPLOYER:
        raise HTTPException(403, "доступно только работодателям")
    return user


CandidateUser = Annotated[User, Depends(require_candidate)]
EmployerUser = Annotated[User, Depends(require_employer)]
