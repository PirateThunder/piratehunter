"""Логика кандидата: профиль (upsert), грейд/кулдауны, снапшоты в core,
привязка ФСП ID."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..constants import grade_rank
from ..core_client.client import CoreClient, CoreError
from ..fsp import service as fsp_service
from ..fsp.client import FspClient
from ..users.models import User
from .constants import GRADE_CONFIRMED, GRADE_UNVERIFIED
from .models import CandidateProfile, GradeState
from .schemas import ProfileIn

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def get_profile(
    session: AsyncSession, user_id: str
) -> CandidateProfile | None:
    return await session.get(CandidateProfile, user_id)


async def get_profile_or_404(
    session: AsyncSession, user_id: str
) -> CandidateProfile:
    profile = await get_profile(session, user_id)
    if profile is None:
        raise HTTPException(404, "профиль не заполнен (PUT /candidate/profile)")
    return profile


async def get_grade_state(
    session: AsyncSession, candidate_id: str
) -> GradeState | None:
    return await session.get(GradeState, candidate_id)


async def upsert_profile(
    session: AsyncSession, user: User, body: ProfileIn
) -> CandidateProfile:
    """Создать/полностью заменить профиль (PUT = upsert)."""
    profile = await session.get(CandidateProfile, user.id)
    if profile is None:
        profile = CandidateProfile(user_id=user.id, fio=body.fio)
        session.add(profile)
    for field in (
        "fio", "phone", "contacts", "stack", "spec_slug", "grade_claimed",
        "experience_years", "roles", "soft_skills", "about",
    ):
        setattr(profile, field, getattr(body, field))
    profile.privacy = body.privacy.model_dump()
    await session.commit()
    return profile


# --- снапшот в core (§4.3): после теста, привязки ФСП, смены профиля ---


def build_snapshot(
    profile: CandidateProfile, grade_state: GradeState | None
) -> dict:
    """Оценочный снапшот — единственное, что читает матчинг core.
    ПДн здесь нет и быть не должно (privacy by design, §4.2).
    test_score не считаем — формула живёт в core (§7.5.2), передаём
    None («вычисли сам» из theta/grade_verified)."""
    return {
        "candidate_id": profile.user_id,
        "spec": profile.spec_slug,
        "grade_verified": grade_state.grade_verified if grade_state else None,
        "theta": grade_state.theta if grade_state else None,
        "test_score": None,
        "fsp_score": profile.fsp_score,
        "stack": list(profile.stack or []),
    }


async def try_push_snapshot(
    core: CoreClient,
    profile: CandidateProfile,
    grade_state: GradeState | None,
) -> None:
    """Best-effort пуш: недоступность core не ломает пользовательский
    сценарий (матчинг просто увидит снапшот при следующем пуше)."""
    if profile.spec_slug is None:
        return  # без специализации снапшот бессмысленен
    try:
        await core.push_snapshot(
            profile.user_id, build_snapshot(profile, grade_state)
        )
    except CoreError:
        logger.warning(
            "snapshot push failed for %s", profile.user_id, exc_info=True
        )


# --- кулдауны грейдов (§7.4.3) ---


def check_test_cooldown(
    grade_state: GradeState | None, grade_target: str
) -> None:
    """409, если тест на grade_target сейчас недоступен по кулдаунам.
    Провал и уход на грейд ниже — без сжигания попытки (Q&A): при
    downgrade_offer тест ниже не проверяет кулдаун смены грейда."""
    if grade_state is None or grade_state.grade_verified is None:
        return  # первичный тест — сразу
    settings = get_settings()
    now = _now()
    verified = grade_state.grade_verified
    if grade_target == verified:
        # повтор теста на текущий грейд — не чаще retest_cooldown_days
        if grade_state.last_test_at is not None:
            available = grade_state.last_test_at + timedelta(
                days=settings.retest_cooldown_days
            )
            if now < available:
                raise HTTPException(
                    409,
                    f"повторный тест на грейд {verified} доступен "
                    f"с {available.date().isoformat()}",
                )
        return
    if (
        grade_state.status == "downgrade_offer"
        and grade_rank(grade_target) < grade_rank(verified)
    ):
        return  # уход ниже после провала — без кулдауна смены грейда
    # смена подтверждённого грейда — не чаще grade_change_cooldown_days
    if grade_state.grade_changed_at is not None:
        available = grade_state.grade_changed_at + timedelta(
            days=settings.grade_change_cooldown_days
        )
        if now < available:
            raise HTTPException(
                409,
                f"смена грейда доступна с {available.date().isoformat()}",
            )


def cooldown_dates(
    grade_state: GradeState | None,
) -> tuple[datetime | None, datetime | None]:
    """(retest_available_at, change_available_at) для GET /candidate/grade."""
    settings = get_settings()
    retest_at = change_at = None
    if grade_state is not None:
        if grade_state.last_test_at is not None:
            retest_at = grade_state.last_test_at + timedelta(
                days=settings.retest_cooldown_days
            )
        if grade_state.grade_changed_at is not None:
            change_at = grade_state.grade_changed_at + timedelta(
                days=settings.grade_change_cooldown_days
            )
    return retest_at, change_at


async def apply_test_result(
    session: AsyncSession,
    core: CoreClient,
    profile: CandidateProfile,
    result: dict,
) -> GradeState:
    """Результат сессии core → GradeState + снапшот. Грейд меняется
    только по результату теста (§6); downgrade не принудителен — core
    отдаёт outcome, grade_verified приходит уже решённым ядром."""
    state = await session.get(GradeState, profile.user_id)
    if state is None:
        state = GradeState(candidate_id=profile.user_id)
        session.add(state)
    now = _now()
    outcome = result.get("outcome") or GRADE_UNVERIFIED
    state.status = outcome
    state.theta = result.get("theta")
    state.last_test_at = now
    verified = result.get("grade_verified")
    if outcome == GRADE_CONFIRMED and verified:
        if verified != state.grade_verified:
            state.grade_changed_at = now
        state.grade_verified = verified
    await session.commit()
    await try_push_snapshot(core, profile, state)
    return state


# --- привязка ФСП ID (§7.9) ---


async def link_fsp(
    session: AsyncSession,
    core: CoreClient,
    fsp: FspClient,
    redis,
    user: User,
    fsp_id: str,
) -> CandidateProfile:
    """Привязка ФСП ID: забор достижений (404 = нет истории → score 0,
    блок не показывается — обязательный кейс ТЗ), fsp_score в профиль,
    снапшот в core. 409, если этот ФСП ID уже у другого юзера."""
    owner = await session.scalar(select(User).where(User.fsp_id == fsp_id))
    if owner is not None and owner.id != user.id:
        raise HTTPException(409, "этот ФСП ID уже привязан к другому аккаунту")
    profile = await get_profile_or_404(session, user.id)
    data, score = await fsp_service.refresh_profile(redis, fsp, fsp_id)
    user.fsp_id = fsp_id
    profile.fsp_data = data
    profile.fsp_score = score
    await session.commit()
    grade_state = await get_grade_state(session, user.id)
    await try_push_snapshot(core, profile, grade_state)
    return profile


async def unlink_fsp(
    session: AsyncSession, core: CoreClient, user: User
) -> CandidateProfile:
    """Отвязка ФСП ID: достижения и score сгорают, снапшот обновлён."""
    profile = await get_profile_or_404(session, user.id)
    user.fsp_id = None
    profile.fsp_data = None
    profile.fsp_score = 0.0
    await session.commit()
    grade_state = await get_grade_state(session, user.id)
    await try_push_snapshot(core, profile, grade_state)
    return profile
