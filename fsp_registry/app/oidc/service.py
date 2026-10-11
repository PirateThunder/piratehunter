"""Логика мок-OIDC «FSP ID»: authorization-code flow поверх синтетических
личностей. Коды одноразовые, живут в памяти процесса с TTL (мок — БД нет).
access/id токены — self-contained JWT HS256 на локальном секрете из env.
"""

import secrets
import time
from dataclasses import dataclass

import jwt
from fastapi import status

from ..config import get_settings
from .constants import IDENTITY_BY_ID
from .exceptions import OAuthError
from .schemas import FspIdentity, TokenResponse, UserInfoResponse


@dataclass
class _AuthCode:
    fsp_id: str
    redirect_uri: str
    client_id: str
    expires_at: float


# одноразовые authorization codes; обмен происходит сразу после выдачи,
# поэтому in-memory словаря достаточно (перезапуск процесса = повтор входа)
_codes: dict[str, _AuthCode] = {}


def validate_client(client_id: str) -> None:
    if client_id != get_settings().oidc_client_id:
        raise OAuthError("invalid_client", f"unknown client_id: {client_id!r}")


def validate_redirect_uri(redirect_uri: str) -> None:
    allowlist = get_settings().redirect_uri_allowlist
    if allowlist and redirect_uri not in allowlist:
        raise OAuthError("invalid_request", "redirect_uri is not allowed")


def issue_code(identity: FspIdentity, redirect_uri: str, client_id: str) -> str:
    code = secrets.token_urlsafe(24)
    _codes[code] = _AuthCode(
        fsp_id=identity.fsp_id,
        redirect_uri=redirect_uri,
        client_id=client_id,
        expires_at=time.time() + get_settings().code_ttl_seconds,
    )
    return code


def exchange_code(code: str, redirect_uri: str, client_id: str) -> FspIdentity:
    stored = _codes.pop(code, None)  # одноразовый: повторный обмен → invalid_grant
    if stored is None or stored.expires_at < time.time():
        raise OAuthError("invalid_grant", "authorization code is invalid or expired")
    if stored.redirect_uri != redirect_uri:
        raise OAuthError("invalid_grant", "redirect_uri does not match the authorize call")
    if stored.client_id != client_id:
        raise OAuthError("invalid_grant", "client_id does not match the authorize call")
    identity = IDENTITY_BY_ID.get(stored.fsp_id)
    if identity is None:  # не должно случаться: коды выдаём только известным
        raise OAuthError("invalid_grant", "unknown identity")
    return identity


def _sign(claims: dict) -> str:
    return jwt.encode(claims, get_settings().jwt_secret, algorithm="HS256")


def issue_tokens(identity: FspIdentity, client_id: str) -> TokenResponse:
    settings = get_settings()
    now = int(time.time())
    base = {
        "iss": settings.issuer,
        "sub": identity.fsp_id,
        "aud": client_id,
        "iat": now,
        "exp": now + settings.token_ttl_seconds,
    }
    access_token = _sign({**base, "typ": "access", "scope": "openid profile email"})
    id_token = _sign(
        {**base, "typ": "id", "name": identity.name, "email": identity.email}
    )
    return TokenResponse(
        access_token=access_token,
        id_token=id_token,
        expires_in=settings.token_ttl_seconds,
    )


def userinfo_from_token(token: str) -> UserInfoResponse:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.oidc_client_id,
        )
    except jwt.PyJWTError as exc:
        raise OAuthError(
            "invalid_token",
            f"access token is invalid: {exc}",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    if claims.get("typ") != "access":
        raise OAuthError(
            "invalid_token",
            "not an access token",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    identity = IDENTITY_BY_ID.get(claims.get("sub", ""))
    if identity is None:
        raise OAuthError(
            "invalid_token",
            "unknown subject",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return UserInfoResponse(
        sub=identity.fsp_id,
        name=identity.name,
        email=identity.email,
        email_verified=True,
    )
