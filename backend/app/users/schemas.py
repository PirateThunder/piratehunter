"""Схемы домена users (кабинет «me» + онбординг роли)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .constants import ROLE_CANDIDATE, ROLE_EMPLOYER


class UserMeOut(BaseModel):
    """Текущий юзер (GET /users/me). role=None — онбординг не пройден."""

    id: str
    email: str | None
    fsp_id: str | None
    role: str | None
    is_verified: bool
    consent_pd: bool
    consent_publish: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleSelectIn(BaseModel):
    """Выбор роли при первом онбординге (§7.1) + согласия 152-ФЗ.

    consent_pd обязателен (без согласия на обработку ПДн платформа
    недоступна); consent_publish — отдельный чекбокс «публиковать
    профиль работодателям» (для кандидата).
    """

    role: Literal[ROLE_CANDIDATE, ROLE_EMPLOYER]
    consent_pd: Literal[True] = Field(
        description="согласие на обработку ПДн (152-ФЗ) — обязательно"
    )
    consent_publish: bool = False
