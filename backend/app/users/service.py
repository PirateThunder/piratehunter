"""Логика пользователей: find-or-create по идентичностям, онбординг."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User


async def find_or_create_by_email(session: AsyncSession, email: str) -> User:
    """Юзер по email: существующий или новый (без роли — онбординг)."""
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, is_verified=True)
        session.add(user)
        await session.commit()
    elif not user.is_verified:
        user.is_verified = True
        await session.commit()
    return user


async def find_or_create_by_fsp_id(session: AsyncSession, fsp_id: str) -> User:
    """Юзер по fsp_id (sub мок-OIDC): существующий или новый (§7.1)."""
    user = await session.scalar(select(User).where(User.fsp_id == fsp_id))
    if user is None:
        user = User(fsp_id=fsp_id, is_verified=True)
        session.add(user)
        await session.commit()
    elif not user.is_verified:
        user.is_verified = True
        await session.commit()
    return user


async def select_role(
    session: AsyncSession,
    user: User,
    role: str,
    consent_pd: bool,
    consent_publish: bool,
) -> User:
    """Онбординг: роль выбирается один раз (повтор — 409)."""
    if user.role is not None:
        raise HTTPException(409, "роль уже выбрана и не меняется")
    user.role = role
    user.consent_pd = consent_pd
    user.consent_publish = consent_publish
    await session.commit()
    return user
