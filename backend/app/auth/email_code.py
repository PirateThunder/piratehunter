"""Вход по коду из письма: генерация/хранение кодов в Redis, лимиты,
SMTP-отправка.

Код — 6 цифр, в Redis лежит sha256 (код не светится в хранилище), TTL
BACK_EMAIL_CODE_TTL. Лимиты: cooldown между запросами на адрес, суточные
квоты на адрес и на IP, ограничение попыток ввода. Без BACK_SMTP_HOST
(локальная разработка) код пишется в лог, а при BACK_ENV=local ещё и
возвращается в dev_code ответа — флоу проходит без почты.
"""

import asyncio
import hashlib
import logging
import secrets
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from redis.asyncio import Redis

from ..config import get_settings

logger = logging.getLogger(__name__)

_CODE_KEY = "ec:code:{email}"
_ATTEMPTS_KEY = "ec:att:{email}"
_COOLDOWN_KEY = "ec:cool:{email}"
_DAY_EMAIL_KEY = "ec:day:{email}:{date}"
_DAY_IP_KEY = "ec:ip:{ip}:{date}"

CODE_LEN = 6


def _s(raw: bytes | str | None) -> str | None:
    """redis.asyncio отдаёт bytes; в тестах FakeRedis — str."""
    if isinstance(raw, bytes):
        return raw.decode()
    return raw


class RateLimited(Exception):
    """Превышен лимит запросов кода (→ 429 с message наружу)."""


class CodeMismatch(Exception):
    """Код не запрошен, истёк, попытки кончились или не совпал (→ 401)."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash(code: str, email: str) -> str:
    return hashlib.sha256(f"{code}:{email}".encode()).hexdigest()


async def request_code(redis: Redis, email: str, ip: str) -> str:
    """Проверить лимиты, сгенерировать и сохранить код → сам код
    (для отправки письмом и dev-поля; в боевом ответе API его нет)."""
    settings = get_settings()
    if await redis.get(_COOLDOWN_KEY.format(email=email)):
        raise RateLimited(
            f"код уже отправлен — повторите через "
            f"{settings.email_code_cooldown} сек"
        )
    date = datetime.now(UTC).strftime("%Y%m%d")
    day_email = await redis.incr(_DAY_EMAIL_KEY.format(email=email, date=date))
    await redis.expire(_DAY_EMAIL_KEY.format(email=email, date=date), 86400)
    if day_email > settings.email_code_daily_per_email:
        raise RateLimited("слишком много кодов на этот адрес за сутки")
    day_ip = await redis.incr(_DAY_IP_KEY.format(ip=ip, date=date))
    await redis.expire(_DAY_IP_KEY.format(ip=ip, date=date), 86400)
    if day_ip > settings.email_code_daily_per_ip:
        raise RateLimited("слишком много запросов с вашего адреса за сутки")

    code = f"{secrets.randbelow(10**CODE_LEN):0{CODE_LEN}d}"
    await redis.setex(
        _CODE_KEY.format(email=email),
        settings.email_code_ttl,
        _hash(code, email),
    )
    if settings.email_code_cooldown > 0:
        await redis.setex(
            _COOLDOWN_KEY.format(email=email),
            settings.email_code_cooldown,
            "1",
        )
    return code


async def verify_code(redis: Redis, email: str, code: str) -> None:
    """Сверить код; при успехе ключи чистятся, при промахе считаются
    попытки (после max код сгорает — запрашивай новый)."""
    settings = get_settings()
    stored = _s(await redis.get(_CODE_KEY.format(email=email)))
    if stored is None:
        raise CodeMismatch("код не запрошен или истёк — запросите новый")
    attempts = int(_s(await redis.get(_ATTEMPTS_KEY.format(email=email))) or 0)
    if attempts >= settings.email_code_max_attempts:
        await redis.delete(_CODE_KEY.format(email=email))
        raise CodeMismatch("попытки кончились — запросите новый код")
    if stored != _hash(code.strip(), email):
        await redis.incr(_ATTEMPTS_KEY.format(email=email))
        await redis.expire(
            _ATTEMPTS_KEY.format(email=email), settings.email_code_ttl
        )
        raise CodeMismatch("неверный код")
    await redis.delete(_CODE_KEY.format(email=email))
    await redis.delete(_ATTEMPTS_KEY.format(email=email))


class SendError(Exception):
    """SMTP не принял письмо (→ 502 наружу)."""


def _send_sync(to: str, code: str) -> None:
    settings = get_settings()
    minutes = settings.email_code_ttl // 60
    msg = EmailMessage()
    msg["Subject"] = f"{code} — код входа в PirateHunter"
    msg["From"] = settings.smtp_from or settings.smtp_user or ""
    msg["To"] = to
    msg.set_content(
        f"Ваш код входа в PirateHunter: {code}\n\n"
        f"Код действует {minutes} минут. "
        "Если вы не запрашивали код — просто проигнорируйте письмо.\n"
    )
    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=15
            ) as smtp:
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password or "")
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(
                settings.smtp_host, settings.smtp_port, timeout=15
            ) as smtp:
                smtp.ehlo()
                smtp.starttls()
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password or "")
                smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as e:
        raise SendError(f"SMTP: {e}") from e


async def send_code(email: str, code: str) -> None:
    """Письмо с кодом; без SMTP-конфига — код в лог (dev-режим)."""
    if not get_settings().smtp_host:
        logger.warning(
            "SMTP не настроен (BACK_SMTP_HOST) — код для %s: %s", email, code
        )
        return
    await asyncio.to_thread(_send_sync, email, code)
