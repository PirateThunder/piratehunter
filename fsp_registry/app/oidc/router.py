"""Эндпоинты мок-OIDC «FSP ID» (PRD §7.1, §8.3).

Флоу входа: backend редиректит браузер на /oidc/authorize (login_hint для
входа одним кликом или форма выбора пользователя) → code → обмен кода на
/oidc/token (server-to-server, httpx) → профиль из /oidc/userinfo.
"""

from html import escape
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Header, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import get_settings
from .constants import DEMO_FSP_ID, IDENTITIES, IDENTITY_BY_ID
from .exceptions import OAuthError
from .schemas import DiscoveryResponse, TokenResponse, UserInfoResponse
from .service import (
    exchange_code,
    issue_code,
    issue_tokens,
    userinfo_from_token,
    validate_client,
    validate_redirect_uri,
)

router = APIRouter(tags=["oidc"])

_FORM_PAGE = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>FSP ID — выбор пользователя</title>
<style>
body {{ font-family: Inter, Arial, sans-serif; max-width: 480px; margin: 48px auto;
       padding: 0 16px; color: #1B1C21; }}
h1 {{ font-size: 22px; margin-bottom: 4px; }}
.hint {{ color: #838388; font-size: 13px; margin-bottom: 24px; }}
a.user {{ display: block; padding: 10px 14px; margin: 6px 0; border: 1px solid #EDEDED;
         border-radius: 12px; text-decoration: none; color: #1B1C21; font-size: 14px; }}
a.user:hover {{ border-color: #402FFF; color: #402FFF; }}
a.user b {{ display: block; }}
a.user span {{ color: #9B9C9E; font-size: 12px; }}
</style></head><body>
<h1>FSP ID</h1>
<p class="hint">Мок-провайдер входа платформы: выберите синтетического пользователя.</p>
{links}
</body></html>"""


def _user_links(query: dict[str, str]) -> str:
    links = []
    for identity in IDENTITIES:
        params = {**query, "login_hint": identity.fsp_id}
        href = f"/oidc/authorize?{urlencode(params)}"
        demo = ' <span>демо, богатая история ФСП</span>' if identity.fsp_id == DEMO_FSP_ID else ""
        links.append(
            f'<a class="user" href="{escape(href)}"><b>{escape(identity.name)}</b>'
            f"<span>{identity.fsp_id} · {escape(identity.email)}</span>{demo}</a>"
        )
    return "\n".join(links)


@router.get(
    "/oidc/authorize",
    status_code=status.HTTP_303_SEE_OTHER,
    summary="OIDC authorize: login_hint → code, иначе HTML-форма выбора",
    response_class=HTMLResponse,
    response_model=None,  # RedirectResponse | HTMLResponse — не pydantic-поле
)
async def authorize(
    client_id: Annotated[str, Query()],
    redirect_uri: Annotated[str, Query()],
    response_type: Annotated[str, Query()] = "code",
    scope: Annotated[str, Query()] = "openid",
    state: Annotated[str | None, Query()] = None,
    login_hint: Annotated[str | None, Query()] = None,
) -> RedirectResponse | HTMLResponse:
    validate_client(client_id)
    validate_redirect_uri(redirect_uri)
    if response_type != "code":
        raise OAuthError("unsupported_response_type", "only response_type=code is supported")

    identity = IDENTITY_BY_ID.get(login_hint) if login_hint else None
    if identity is None:
        query: dict[str, str] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": response_type,
            "scope": scope,
        }
        if state is not None:
            query["state"] = state
        return HTMLResponse(_FORM_PAGE.format(links=_user_links(query)))

    code = issue_code(identity, redirect_uri, client_id)
    params = {"code": code}
    if state is not None:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        url=f"{redirect_uri}{sep}{urlencode(params)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/oidc/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="OIDC token: обмен authorization code на id/access токены",
)
async def token(
    grant_type: Annotated[str, Form()],
    code: Annotated[str, Form()],
    redirect_uri: Annotated[str, Form()],
    client_id: Annotated[str, Form()],
) -> TokenResponse:
    validate_client(client_id)
    if grant_type != "authorization_code":
        raise OAuthError("unsupported_grant_type", "only authorization_code is supported")
    identity = exchange_code(code, redirect_uri, client_id)
    return issue_tokens(identity, client_id)


@router.get(
    "/oidc/userinfo",
    response_model=UserInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="OIDC userinfo: sub=fsp_id, name, email",
)
async def userinfo(
    authorization: Annotated[str | None, Header()] = None,
) -> UserInfoResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise OAuthError(
            "invalid_token",
            "expected Authorization: Bearer <access_token>",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return userinfo_from_token(authorization.removeprefix("Bearer ").strip())


@router.get(
    "/.well-known/openid-configuration",
    response_model=DiscoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="OIDC discovery (минимальный, Keycloak-совместимый по форме)",
)
async def discovery() -> DiscoveryResponse:
    issuer = get_settings().issuer
    return DiscoveryResponse(
        issuer=issuer,
        authorization_endpoint=f"{issuer}/oidc/authorize",
        token_endpoint=f"{issuer}/oidc/token",
        userinfo_endpoint=f"{issuer}/oidc/userinfo",
        response_types_supported=["code"],
        grant_types_supported=["authorization_code"],
        subject_types_supported=["public"],
        id_token_signing_alg_values_supported=["HS256"],
        scopes_supported=["openid", "profile", "email"],
    )
