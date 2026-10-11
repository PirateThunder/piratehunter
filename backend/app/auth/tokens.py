"""JWT-токены сессии: access (15 мин) + refresh (30 дней).

HS256, sub=user_id, type=access|refresh. Секрет — BACK_JWT_SECRET с
фолбэком на встроенный dev-дефолт. Refresh — stateless (без серверного
хранилища; ротация = перевыпуск пары по живому refresh).
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from ..config import get_settings
from ..users.models import User

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)

_ALGO = "HS256"

TYPE_ACCESS = "access"
TYPE_REFRESH = "refresh"


def _secret() -> str:
    return get_settings().jwt_secret or "piratehunter-dev-jwt-secret-change-me"


def _now() -> datetime:
    # aware-время: .timestamp() у naive datetime трактует его как локальное
    return datetime.now(UTC)


def _issue(user_id: str, type_: str, ttl: timedelta) -> str:
    now = _now()
    payload = {
        "sub": user_id,
        "type": type_,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def issue_pair(user: User) -> tuple[str, str, int]:
    """(access_token, refresh_token, expires_in) для юзера."""
    access = _issue(user.id, TYPE_ACCESS, ACCESS_TTL)
    refresh = _issue(user.id, TYPE_REFRESH, REFRESH_TTL)
    return access, refresh, int(ACCESS_TTL.total_seconds())


class TokenError(Exception):
    """Невалидный/просроченный токен или не тот тип."""


def verify(token: str, type_: str) -> str:
    """user_id (sub) из валидного токена нужного типа; иначе TokenError."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGO])
    except jwt.PyJWTError as e:
        raise TokenError(str(e)) from e
    if payload.get("type") != type_:
        raise TokenError("не тот тип токена")
    sub = payload.get("sub")
    if not sub:
        raise TokenError("пустой sub")
    return str(sub)
