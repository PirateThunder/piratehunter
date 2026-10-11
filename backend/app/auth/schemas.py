"""Схемы auth-ручек (/api/v1/auth/*)."""

from pydantic import BaseModel, Field

EMAIL_RE = r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$"


class EmailRequestIn(BaseModel):
    """Тело POST /auth/email/request: адрес для отправки кода."""

    email: str = Field(min_length=3, max_length=320, pattern=EMAIL_RE)


class EmailRequestOut(BaseModel):
    detail: str
    # локальная разработка без SMTP (BACK_ENV=local): код возвращается
    # в ответе, чтобы флоу проходил без почты; вне local — всегда None
    dev_code: str | None = None


class EmailVerifyIn(BaseModel):
    """Тело POST /auth/email/verify: код из письма."""

    email: str = Field(min_length=3, max_length=320, pattern=EMAIL_RE)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class FspCallbackIn(BaseModel):
    """Тело POST /auth/fsp/callback: code+state со страницы редиректа
    мок-OIDC fsp_registry (фронт принимает их на fsp_redirect_uri)."""

    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=256)


class FspAuthorizeOut(BaseModel):
    """GET /auth/fsp/authorize: куда вести браузер + выданный state."""

    authorize_url: str
    state: str


class DevLoginIn(BaseModel):
    """Dev-login фиксированными демо-аккаунтами (§10): кандидат,
    кандидат с ФСП-историей, работодатель."""

    account: str = Field(min_length=1, max_length=64)


class AuthUserOut(BaseModel):
    id: str
    email: str | None
    fsp_id: str | None
    role: str | None
    is_verified: bool

    model_config = {"from_attributes": True}


class AuthPairOut(BaseModel):
    """Ответ логина/рефреша: access в теле, refresh — httpOnly cookie."""

    user: AuthUserOut
    access_token: str
    expires_in: int  # сек, access TTL
