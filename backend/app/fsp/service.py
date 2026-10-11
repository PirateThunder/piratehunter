"""Достижения ФСП с кэшем в Redis (реестр не дёргаем на каждый показ
профиля; 404 = «нет истории» кэшируется тоже — обязательный кейс ТЗ)."""

import json
import logging

from redis.asyncio import Redis

from ..config import get_settings
from .client import FspClient
from .scoring import compute_fsp_score

logger = logging.getLogger(__name__)

_CACHE_KEY = "fsp:prof:{fsp_id}"
_CACHE_MISS = "null"


async def get_profile_cached(
    redis: Redis, client: FspClient, fsp_id: str
) -> dict | None:
    """Профиль достижений | None (нет истории / реестр отвечает 404).
    Ошибки транспорта пробрасываем — вызывающий решает (профиль юзера
    покажем и без достижений, линк ФСП — упадёт 502)."""
    key = _CACHE_KEY.format(fsp_id=fsp_id)
    raw = await redis.get(key)
    if isinstance(raw, bytes):
        raw = raw.decode()
    if raw is not None:
        return None if raw == _CACHE_MISS else json.loads(raw)
    profile = await client.get_profile(fsp_id)
    ttl = get_settings().fsp_profile_cache_ttl
    await redis.setex(
        key, ttl, _CACHE_MISS if profile is None else json.dumps(profile)
    )
    return profile


async def refresh_profile(
    redis: Redis, client: FspClient, fsp_id: str
) -> tuple[dict | None, float]:
    """Принудительный забор (привязка FSP ID, вход через FSP ID):
    кэш перезаписывается. → (профиль | None, fsp_score)."""
    profile = await client.get_profile(fsp_id)
    ttl = get_settings().fsp_profile_cache_ttl
    key = _CACHE_KEY.format(fsp_id=fsp_id)
    await redis.setex(
        key, ttl, _CACHE_MISS if profile is None else json.dumps(profile)
    )
    return profile, compute_fsp_score(profile)
