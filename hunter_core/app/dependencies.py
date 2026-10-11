"""Общие зависимости core-api: internal-токен, банк заданий, сессия БД."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import UnauthorizedError
from itembank.registry import BankRegistry


async def verify_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    """Проверка X-Internal-Token; если CORE_INTERNAL_TOKEN не задан — пропускаем (dev)."""
    token = get_settings().internal_token
    if token and x_internal_token != token:
        raise UnauthorizedError()


def get_bank(request: Request) -> BankRegistry:
    return request.app.state.bank


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session
