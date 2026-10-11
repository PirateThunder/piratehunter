"""Схемы мок-OIDC «FSP ID». Контракт приближен к OIDC (PRD §8.3), чтобы
переезд на боевой Keycloak был сменой base_url и client-конфига backend."""

from pydantic import BaseModel


class FspIdentity(BaseModel):
    fsp_id: str
    name: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    id_token: str
    token_type: str = "Bearer"
    expires_in: int


class UserInfoResponse(BaseModel):
    sub: str  # = fsp_id
    name: str
    email: str
    email_verified: bool


class DiscoveryResponse(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    response_types_supported: list[str]
    grant_types_supported: list[str]
    subject_types_supported: list[str]
    id_token_signing_alg_values_supported: list[str]
    scopes_supported: list[str]
