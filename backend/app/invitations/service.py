"""Логика приглашений и ПРАВИЛО ВИДИМОСТИ КОНТАКТОВ (PRD §7.6).

can_view_contacts / contacts_allowed_ids — единственная точка решения
«открыты ли контакты кандидата этой компании»: accepted-приглашение
от компании (в фазе 2 добавится Application от кандидата — правило
расширяется здесь, сериализаторы не трогаем). Роутеры решение не
дублируют.
"""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..candidates.models import CandidateProfile
from ..companies.models import Company
from ..config import get_settings
from ..users.constants import ROLE_CANDIDATE
from ..users.models import User
from .constants import ACCEPTED, DECLINED, OPEN_STATUSES, SENT, VIEWED
from .models import Invitation
from .schemas import InvitationCreateIn

logger = logging.getLogger(__name__)

_RATE_KEY = "inv:rate:{company_id}:{hour}"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# --- правило видимости §7.6 ---


async def contacts_allowed_ids(
    session: AsyncSession, company_id: str, candidate_ids: list[str]
) -> set[str]:
    """Кандидаты из списка, чьи контакты открыты ЭТОЙ компании:
    есть приглашение компании в статусе accepted. (Фаза 2: + отклик
    Application кандидата на вакансию компании — §7.6.)"""
    if not candidate_ids:
        return set()
    result = await session.scalars(
        select(Invitation.candidate_id).where(
            Invitation.company_id == company_id,
            Invitation.candidate_id.in_(candidate_ids),
            Invitation.status == ACCEPTED,
        )
    )
    return set(result)


async def can_view_contacts(
    session: AsyncSession, company_id: str, candidate_id: str
) -> bool:
    return bool(
        await contacts_allowed_ids(session, company_id, [candidate_id])
    )


# --- создание (работодатель) ---


async def _check_rate_limit(redis: Redis, company_id: str) -> None:
    """Лимит создания приглашений (NFR §12): N в час на компанию."""
    settings = get_settings()
    if settings.invitation_rate_per_hour <= 0:
        return
    hour = _now().strftime("%Y%m%d%H")
    key = _RATE_KEY.format(company_id=company_id, hour=hour)
    count = await redis.incr(key)
    await redis.expire(key, 3600)
    if count > settings.invitation_rate_per_hour:
        raise HTTPException(
            429, "слишком много приглашений — попробуйте позже"
        )


async def create(
    session: AsyncSession,
    redis: Redis,
    company_id: str,
    body: InvitationCreateIn,
) -> Invitation:
    candidate = await session.get(User, body.candidate_id)
    if (
        candidate is None
        or candidate.role != ROLE_CANDIDATE
        or await session.get(CandidateProfile, candidate.id) is None
    ):
        raise HTTPException(404, "кандидат не найден")
    await _check_rate_limit(redis, company_id)
    invitation = Invitation(company_id=company_id, **body.model_dump())
    session.add(invitation)
    await session.commit()
    return invitation


# --- списки ---


async def list_for_employer(
    session: AsyncSession, company_id: str
) -> list[Invitation]:
    result = await session.scalars(
        select(Invitation)
        .where(Invitation.company_id == company_id)
        .order_by(Invitation.created_at.desc())
    )
    return list(result)


async def list_for_candidate(
    session: AsyncSession, candidate_id: str
) -> list[Invitation]:
    """Входящие кандидата. Открытие списка = просмотр: sent → viewed
    (§7.6, «viewed при первом открытии кандидатом»)."""
    await session.execute(
        update(Invitation)
        .where(
            Invitation.candidate_id == candidate_id,
            Invitation.status == SENT,
        )
        .values(status=VIEWED, status_at=_now())
    )
    result = await session.scalars(
        select(Invitation)
        .where(Invitation.candidate_id == candidate_id)
        .order_by(Invitation.created_at.desc())
    )
    invitations = list(result)
    await session.commit()
    return invitations


# --- переходы статусов (кандидат) ---


async def _get_own(
    session: AsyncSession, candidate_id: str, invitation_id: str
) -> Invitation:
    invitation = await session.get(Invitation, invitation_id)
    if invitation is None or invitation.candidate_id != candidate_id:
        raise HTTPException(404, "приглашение не найдено")
    return invitation


async def transition(
    session: AsyncSession,
    candidate_id: str,
    invitation_id: str,
    target: str,
) -> Invitation:
    """accept/decline: только из открытых статусов (sent|viewed),
    повторный ответ — 409."""
    invitation = await _get_own(session, candidate_id, invitation_id)
    if invitation.status not in OPEN_STATUSES:
        raise HTTPException(
            409, f"приглашение уже закрыто (статус {invitation.status})"
        )
    invitation.status = target
    invitation.status_at = _now()
    await session.commit()
    return invitation


async def accept(
    session: AsyncSession, candidate_id: str, invitation_id: str
) -> Invitation:
    return await transition(session, candidate_id, invitation_id, ACCEPTED)


async def decline(
    session: AsyncSession, candidate_id: str, invitation_id: str
) -> Invitation:
    return await transition(session, candidate_id, invitation_id, DECLINED)


# --- джойны для сериализации ---


async def load_companies(
    session: AsyncSession, company_ids: list[str]
) -> dict[str, Company]:
    if not company_ids:
        return {}
    return {
        c.user_id: c
        for c in await session.scalars(
            select(Company).where(Company.user_id.in_(company_ids))
        )
    }
