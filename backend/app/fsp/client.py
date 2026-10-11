"""HTTP-клиент fsp_registry (мок-реестр достижений ФСП + мок-OIDC
«FSP ID») — единственная точка связи, контракт PRD §8.3.

Контракт приближен к OIDC, чтобы переезд на боевой Keycloak был
сменой конфига (base_url + client), а не кода (PRD §7.1).
"""

import logging
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from fastapi import Depends

from ..config import get_settings

logger = logging.getLogger(__name__)


class FspError(Exception):
    """Ошибка вызова fsp_registry."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FspClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        public_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.fsp_registry_url).rstrip("/")
        # browser-facing база для authorize_url: при явном base_url (тесты)
        # совпадает с ним, иначе — отдельный публичный адрес из конфига
        fallback = settings.fsp_public_url if base_url is None else None
        self._public_url = (public_url or fallback or self._base_url).rstrip(
            "/"
        )
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(10.0),
            transport=transport,
            # внутренний трафик не уходит в прокси из окружения
            trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        try:
            resp = await self._client.request(method, url, **kwargs)
        except httpx.TransportError as e:
            raise FspError(f"fsp_registry недоступен: {e}") from e
        if resp.status_code >= 400:
            raise FspError(
                f"fsp_registry ответил {resp.status_code}: "
                f"{resp.text[:300]}",
                status_code=resp.status_code,
            )
        return resp

    # --- мок-OIDC «FSP ID» (§8.3) ---

    def build_authorize_url(self, state: str, fsp_id: str | None = None) -> str:
        """URL, куда фронт ведёт браузер: GET /oidc/authorize → редирект
        на redirect_uri с code+state (автовыбор демо-профиля или явный
        fsp_id). База — публичная (browser-facing), не внутренняя."""
        settings = get_settings()
        params = {
            "response_type": "code",
            "client_id": settings.fsp_client_id,
            "redirect_uri": settings.fsp_redirect_uri,
            "scope": "openid profile",
            "state": state,
        }
        if fsp_id:
            # OIDC-имя параметра на стороне реестра — login_hint
            params["login_hint"] = fsp_id
        return f"{self._public_url}/oidc/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """POST /oidc/token (form, как в OIDC) → {access_token, ...}."""
        settings = get_settings()
        resp = await self._request(
            "POST",
            "/oidc/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.fsp_redirect_uri,
                "client_id": settings.fsp_client_id,
                "client_secret": settings.fsp_client_secret or "",
            },
        )
        return resp.json()

    async def userinfo(self, access_token: str) -> dict:
        """GET /oidc/userinfo → профиль (sub = fsp_id, достижения)."""
        resp = await self._request(
            "GET",
            "/oidc/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return resp.json()

    # --- реестр достижений ---

    async def get_profile(self, fsp_id: str) -> dict | None:
        """GET /fsp/v1/profiles/{fsp_id} → достижения | None (404 =
        «нет истории ФСП» — обязательный кейс ТЗ, не ошибка)."""
        try:
            resp = await self._request("GET", f"/fsp/v1/profiles/{fsp_id}")
        except FspError as e:
            if e.status_code == 404:
                return None
            raise
        return resp.json()


_client: FspClient | None = None


def get_fsp_client() -> FspClient:
    global _client
    if _client is None:
        _client = FspClient()
    return _client


FspDep = Annotated[FspClient, Depends(get_fsp_client)]
