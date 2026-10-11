"""Redis: коды подтверждения, лимиты, OIDC state, кэш достижений ФСП."""

from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis

from .config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url)
    return _redis


RedisDep = Annotated[Redis, Depends(get_redis)]
