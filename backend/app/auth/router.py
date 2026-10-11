"""Ручки авторизации (/api/v1/auth/*), PRD §7.1.

Три провайдера за общим флоу «получить подтверждённую идентичность →
find-or-create User → JWT-пара» (задел под боевой Keycloak третьим
провайдером сменой конфига):

- email-код: request (лимиты, SMTP/лог/dev_code) → verify;
- «FSP ID»: мок-OIDC authorization-code flow против fsp_registry
  (authorize → callback → token → userinfo → User по sub=fsp_id);
- dev-login фиксированными демо-аккаунтами (BACK_AUTH_DEV_LOGIN=1).

Access — в теле (Bearer), refresh — httpOnly cookie ph_refresh
(path=/api/v1/auth, SameSite=Lax, secure вне local). Ротация refresh
на /refresh. Роль выбирается при первом онбординге (POST /users/me/role).
"""

import logging
import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from ..config import get_settings
from ..database import DbDep
from ..fsp.client import FspDep
from ..fsp.service import refresh_profile
from ..redis import RedisDep
from ..users import service as users_service
from ..users.models import User
from . import email_code, tokens
from .constants import COOKIE_PATH, DEV_ACCOUNTS, REFRESH_COOKIE, state_key
from .dependencies import OptionalUser
from .schemas import (
    AuthPairOut,
    AuthUserOut,
    DevLoginIn,
    EmailRequestIn,
    EmailRequestOut,
    EmailVerifyIn,
    FspAuthorizeOut,
    FspCallbackIn,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


def _set_refresh_cookie(response: Response, refresh: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=int(tokens.REFRESH_TTL.total_seconds()),
        path=COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=get_settings().env != "local",
    )


def _pair_response(user: User, response: Response) -> AuthPairOut:
    access, refresh, expires_in = tokens.issue_pair(user)
    _set_refresh_cookie(response, refresh)
    return AuthPairOut(
        user=AuthUserOut.model_validate(user),
        access_token=access,
        expires_in=expires_in,
    )


def _check_not_banned(user: User) -> None:
    if user.is_banned:
        raise HTTPException(403, "пользователь заблокирован")


# --- email-код (альтернативный канал регистрации, §7.1) ---


@router.post(
    "/auth/email/request",
    response_model=EmailRequestOut,
    status_code=202,
    summary="Запросить код входа на email",
)
async def auth_email_request(
    body: EmailRequestIn, request: Request, redis: RedisDep
) -> EmailRequestOut:
    """Код входа на почту: лимиты (cooldown + суточные), генерация,
    SMTP-отправка. Ответ одинаковый для любых адресов; без SMTP и при
    BACK_ENV=local код дополнительно возвращается в dev_code."""
    settings = get_settings()
    email = email_code.normalize_email(body.email)
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = ip or (request.client.host if request.client else "unknown")
    try:
        code = await email_code.request_code(redis, email, ip)
    except email_code.RateLimited as e:
        raise HTTPException(429, str(e)) from e
    try:
        await email_code.send_code(email, code)
    except email_code.SendError as e:
        raise HTTPException(
            502, "не удалось отправить письмо — попробуйте позже"
        ) from e
    dev_code = (
        code if settings.env == "local" and not settings.smtp_host else None
    )
    return EmailRequestOut(
        detail="код отправлен, проверьте почту", dev_code=dev_code
    )


@router.post(
    "/auth/email/verify",
    response_model=AuthPairOut,
    summary="Войти по коду из письма",
)
async def auth_email_verify(
    body: EmailVerifyIn,
    session: DbDep,
    redis: RedisDep,
    response: Response,
    current: OptionalUser = None,
) -> AuthPairOut:
    """Вход по коду: find-or-create по email. С Bearer-токеном —
    привязка почты к текущему аккаунту вместо входа (409, если почта
    занята другим юзером)."""
    email = email_code.normalize_email(body.email)
    try:
        await email_code.verify_code(redis, email, body.code)
    except email_code.CodeMismatch as e:
        raise HTTPException(401, str(e)) from e

    if current is not None:
        if current.email == email:
            return _pair_response(current, response)
        owner = await session.scalar(select(User).where(User.email == email))
        if owner is not None and owner.id != current.id:
            raise HTTPException(409, "почта уже привязана к другому аккаунту")
        if current.email:
            raise HTTPException(409, "к аккаунту уже привязана другая почта")
        current.email = email
        current.is_verified = True
        await session.commit()
        return _pair_response(current, response)

    user = await users_service.find_or_create_by_email(session, email)
    _check_not_banned(user)
    return _pair_response(user, response)


# --- вход через FSP ID (мок-OIDC, ожидаемый сценарий §7.1) ---


@router.get(
    "/auth/fsp/authorize",
    response_model=FspAuthorizeOut,
    summary="Начать вход через FSP ID",
)
async def auth_fsp_authorize(
    redis: RedisDep, fsp: FspDep, fsp_id: str | None = None
) -> FspAuthorizeOut:
    """Выдать state и URL мок-OIDC authorize fsp_registry. Фронт ведёт
    браузер по authorize_url; реестр вернёт code+state на
    BACK_FSP_REDIRECT_URI. fsp_id — необязательный явный выбор профиля
    (иначе реестр автовыбирает демо-профиль)."""
    settings = get_settings()
    state = secrets.token_urlsafe(16)
    await redis.setex(state_key(state), settings.fsp_state_ttl, "1")
    return FspAuthorizeOut(
        authorize_url=fsp.build_authorize_url(state, fsp_id=fsp_id),
        state=state,
    )


async def _complete_fsp_login(
    code: str,
    state: str,
    session: DbDep,
    redis: RedisDep,
    fsp: FspDep,
) -> User:
    """Обмен кода на токен → userinfo → User по sub (fsp_id).
    Достижения подтягиваются сразу (кэш, §7.1); недоступность реестра
    достижений входу не мешает."""
    stored = await redis.get(state_key(state))
    if stored is None:
        raise HTTPException(401, "state неизвестен или истёк — начните заново")
    await redis.delete(state_key(state))
    try:
        token_data = await fsp.exchange_code(code)
        info = await fsp.userinfo(token_data["access_token"])
    except Exception as e:
        raise HTTPException(401, f"FSP ID: не удалось подтвердить код: {e}") from e
    fsp_id = info.get("sub") or info.get("fsp_id")
    if not fsp_id:
        raise HTTPException(502, "FSP ID: userinfo без sub")
    user = await users_service.find_or_create_by_fsp_id(session, str(fsp_id))
    _check_not_banned(user)
    try:
        await refresh_profile(redis, fsp, str(fsp_id))
    except Exception:
        logger.warning("fsp achievements prefetch failed for %s", fsp_id)
    return user


@router.post(
    "/auth/fsp/callback",
    response_model=AuthPairOut,
    summary="Завершить вход через FSP ID",
)
async def auth_fsp_callback(
    body: FspCallbackIn,
    session: DbDep,
    redis: RedisDep,
    response: Response,
    fsp: FspDep,
) -> AuthPairOut:
    """API-вариант завершения: code+state в теле → JWT-пара в ответе."""
    user = await _complete_fsp_login(body.code, body.state, session, redis, fsp)
    return _pair_response(user, response)


@router.get(
    "/auth/fsp/callback",
    response_class=RedirectResponse,
    summary="Callback FSP ID (browser redirect из реестра)",
)
async def auth_fsp_callback_redirect(
    code: str,
    state: str,
    session: DbDep,
    redis: RedisDep,
    fsp: FspDep,
) -> RedirectResponse:
    """Браузерный вариант: реестр вернул сюда code+state (redirect_uri на
    origin фронта, Next проксирует /api/*). Ставим refresh-cookie и
    уводим браузер на /login/callback — сессию поднимет bootstrap."""
    settings = get_settings()
    try:
        user = await _complete_fsp_login(code, state, session, redis, fsp)
    except HTTPException:
        return RedirectResponse(
            f"{settings.front_url}/login?error=fsp", status_code=303
        )
    _, refresh, _ = tokens.issue_pair(user)
    redirect = RedirectResponse(
        f"{settings.front_url}/login/callback", status_code=303
    )
    _set_refresh_cookie(redirect, refresh)
    return redirect


# --- dev-login (только BACK_AUTH_DEV_LOGIN=1) ---


@router.post(
    "/auth/dev",
    response_model=AuthPairOut,
    summary="Dev-login фиксированным демо-аккаунтом",
)
async def auth_dev(
    body: DevLoginIn, session: DbDep, response: Response
) -> AuthPairOut:
    """Быстрый вход демо-аккаунтами §10 (candidate / candidate-fsp /
    employer). Только BACK_AUTH_DEV_LOGIN=1; иначе 404."""
    if not get_settings().auth_dev_login:
        raise HTTPException(404, "dev-login выключен")
    spec = DEV_ACCOUNTS.get(body.account)
    if spec is None:
        raise HTTPException(
            422,
            f"неизвестный демо-аккаунт; доступны: {sorted(DEV_ACCOUNTS)}",
        )
    user = await session.scalar(
        select(User).where(User.email == spec["email"])
    )
    if user is None:
        user = User(
            email=spec["email"],
            fsp_id=spec["fsp_id"],
            role=spec["role"],
            is_verified=True,
            consent_pd=True,
            consent_publish=True,
        )
        session.add(user)
        await session.commit()
    _check_not_banned(user)
    return _pair_response(user, response)


# --- refresh / logout ---


@router.post(
    "/auth/refresh",
    response_model=AuthPairOut,
    summary="Обновить JWT-пару по refresh-cookie",
)
async def auth_refresh(
    request: Request, session: DbDep, response: Response
) -> AuthPairOut:
    """Новая пара по refresh-cookie (ротация: stateless, хранилища
    отозванных нет — пара перевыпускается по живому refresh)."""
    refresh = request.cookies.get(REFRESH_COOKIE)
    if not refresh:
        raise HTTPException(401, "нет refresh-cookie")
    try:
        user_id = tokens.verify(refresh, tokens.TYPE_REFRESH)
    except tokens.TokenError:
        raise HTTPException(
            401, "refresh-токен невалиден или истёк — войдите заново"
        ) from None
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(401, "пользователь токена не найден")
    _check_not_banned(user)
    return _pair_response(user, response)


@router.post("/auth/logout", status_code=204, summary="Выйти")
async def auth_logout(response: Response) -> None:
    """Выход: чистим refresh-cookie (access просто перестаём слать)."""
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
