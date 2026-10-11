"""Логика потребностей: CRUD с проверкой владельца, LLM-авто-парсинг
raw_text при создании («мы поняли так», §7.3), подборка через core
match + джойн профилей с правилами видимости §7.6."""

import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..candidates import visibility
from ..candidates.models import CandidateProfile, GradeState
from ..constants import GRADES, SPECIALIZATIONS
from ..core_client.client import CoreClient, CoreError
from ..invitations import service as invitations_service
from ..users.models import User
from .models import Need
from .schemas import NeedIn, ShortlistItemOut

logger = logging.getLogger(__name__)


async def get_own(session: AsyncSession, company_id: str, need_id: str) -> Need:
    need = await session.get(Need, need_id)
    if need is None or need.company_id != company_id:
        raise HTTPException(404, "потребность не найдена")
    return need


async def _try_parse(core: CoreClient, raw_text: str) -> dict | None:
    """LLM-разбор raw_text в core (best-effort): core down/ошибка —
    parsed=None, создание потребности не страдает."""
    try:
        return await core.llm_parse_need(raw_text)
    except CoreError:
        logger.warning("llm_parse_need failed", exc_info=True)
        return None


async def create(
    session: AsyncSession, core: CoreClient, company_id: str, body: NeedIn
) -> Need:
    """Создание потребности. Парсинг raw_text сохраняем в parsed всегда
    (UI «мы поняли так»); если spec_slug не указан — подставляем
    spec/grade/stack из парсинга в незаполненные поля, если указан явно
    — поля не перетираем."""
    data = body.model_dump()
    parsed = await _try_parse(core, body.raw_text)
    if parsed is not None and body.spec_slug is None:
        spec = parsed.get("spec")
        if spec in SPECIALIZATIONS:
            data["spec_slug"] = spec
        grade = parsed.get("grade")
        if grade in GRADES:
            data["grade"] = grade
        if not data["stack_must"]:
            data["stack_must"] = list(parsed.get("stack_must") or [])
        if not data["stack_nice"]:
            data["stack_nice"] = list(parsed.get("stack_nice") or [])
    need = Need(company_id=company_id, parsed=parsed, **data)
    session.add(need)
    await session.commit()
    return need


async def list_own(session: AsyncSession, company_id: str) -> list[Need]:
    result = await session.scalars(
        select(Need)
        .where(Need.company_id == company_id)
        .order_by(Need.created_at.desc())
    )
    return list(result)


async def update(
    session: AsyncSession, company_id: str, need_id: str, body: NeedIn
) -> Need:
    need = await get_own(session, company_id, need_id)
    for field, value in body.model_dump().items():
        setattr(need, field, value)
    await session.commit()
    return need


async def delete(session: AsyncSession, company_id: str, need_id: str) -> None:
    need = await get_own(session, company_id, need_id)
    await session.delete(need)
    await session.commit()


async def shortlist(
    session: AsyncSession, core: CoreClient, company_id: str, need_id: str
) -> tuple[Need, list[ShortlistItemOut]]:
    """Подборка по потребности: core match (оркестрация, §7.5) → джойн
    профилей → правила видимости (контакты — только после accept)."""
    need = await get_own(session, company_id, need_id)
    try:
        ranked = await core.match(
            {
                "raw_text": need.raw_text,
                "spec": need.spec_slug,  # имя поля в контракте core — spec
                "grade": need.grade,
                "stack_must": list(need.stack_must or []),
                "stack_nice": list(need.stack_nice or []),
                "salary_from": need.salary_from,
                "salary_to": need.salary_to,
            }
        )
    except CoreError as e:
        raise HTTPException(502, f"core-api: {e}") from e

    candidate_ids = [r.get("candidate_id") for r in ranked]
    profiles = {
        p.user_id: p
        for p in await session.scalars(
            select(CandidateProfile).where(
                CandidateProfile.user_id.in_(candidate_ids)
            )
        )
    }
    users = {
        u.id: u
        for u in await session.scalars(
            select(User).where(User.id.in_(candidate_ids))
        )
    }
    grade_states = {
        g.candidate_id: g
        for g in await session.scalars(
            select(GradeState).where(GradeState.candidate_id.in_(candidate_ids))
        )
    }
    # правило §7.6 одним запросом: у каких кандидатов уже есть accept
    # от этой компании — им контакты открыты
    allowed = await invitations_service.contacts_allowed_ids(
        session, company_id, candidate_ids
    )

    items: list[ShortlistItemOut] = []
    for row in ranked:
        cid = row.get("candidate_id")
        profile = profiles.get(cid)
        user = users.get(cid)
        if profile is None or user is None:
            continue  # снапшот есть, а профиля нет — пропускаем
        items.append(
            ShortlistItemOut(
                candidate=visibility.to_employer_view(
                    profile,
                    user,
                    grade_states.get(cid),
                    contacts_allowed=cid in allowed,
                ),
                score=row.get("score", 0.0),
                explanation=row.get("explanation"),
            )
        )
    return need, items
