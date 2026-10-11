"""Рыночная аналитика вилок (PRD §7.5.5): агрегация ЗП-вилок платформы
по категории spec×grade.

Источники выборки:
- потребности (need.spec_slug + need.grade, обе границы заданы);
- приглашения: категория кандидата — candidate_profile.spec_slug +
  grade_verified (подтверждённый) else grade_claimed. (Колонки
  invitation.need_id в схеме фазы 1 нет — привязка приглашения к
  потребности появится с вакансиями фазы 2, §7.7.)

Перцентили считаются Python-side (линейная интерполяция — тот же
результат, что percentile_cont на PG) одной функцией для обеих СУБД:
тесты на sqlite гоняют ровно боевую логику.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..candidates.models import CandidateProfile, GradeState
from ..core_client.client import CoreClient, CoreError
from ..invitations.models import Invitation
from ..needs.models import Need
from .schemas import SalaryStatsOut

logger = logging.getLogger(__name__)


def percentile(values: list[float], q: float) -> float | None:
    """q-й перцентиль (0..1) с линейной интерполяцией (метод
    PERCENTILE_CONT); пустая выборка → None."""
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


async def _need_salaries(
    session: AsyncSession, spec: str, grade: str
) -> list[tuple[int, int]]:
    rows = await session.execute(
        select(Need.salary_from, Need.salary_to).where(
            Need.spec_slug == spec,
            Need.grade == grade,
            Need.salary_from.is_not(None),
            Need.salary_to.is_not(None),
        )
    )
    return [(f, t) for f, t in rows.all()]


async def _invitation_salaries(
    session: AsyncSession, spec: str, grade: str
) -> list[tuple[int, int]]:
    """Вилки приглашений в категории кандидата: spec из профиля,
    грейд — подтверждённый (grade_state), иначе заявляемый."""
    effective_grade = func.coalesce(
        GradeState.grade_verified, CandidateProfile.grade_claimed
    )
    rows = await session.execute(
        select(Invitation.salary_from, Invitation.salary_to)
        .join(
            CandidateProfile,
            CandidateProfile.user_id == Invitation.candidate_id,
        )
        .outerjoin(
            GradeState, GradeState.candidate_id == Invitation.candidate_id
        )
        .where(
            CandidateProfile.spec_slug == spec,
            effective_grade == grade,
        )
    )
    return [(f, t) for f, t in rows.all()]


async def _category_size(
    core: CoreClient, spec: str, grade: str
) -> int | None:
    """Размер категории из core-ранжирования; best-effort — core down
    не мешает ответу (§16: аналитика не критичный путь)."""
    try:
        return len(await core.category_ranking(spec, grade))
    except CoreError:
        logger.warning("category_ranking failed for %s/%s", spec, grade)
        return None


async def salary_stats(
    session: AsyncSession, core: CoreClient, spec: str, grade: str
) -> SalaryStatsOut:
    needs = await _need_salaries(session, spec, grade)
    invitations = await _invitation_salaries(session, spec, grade)
    all_from = [f for f, _ in needs] + [f for f, _ in invitations]
    all_to = [t for _, t in needs] + [t for _, t in invitations]
    return SalaryStatsOut(
        spec=spec,
        grade=grade,
        category_size=await _category_size(core, spec, grade),
        sample_needs=len(needs),
        sample_invitations=len(invitations),
        from_p25=percentile(all_from, 0.25),
        from_p50=percentile(all_from, 0.50),
        from_p75=percentile(all_from, 0.75),
        to_p25=percentile(all_to, 0.25),
        to_p50=percentile(all_to, 0.50),
        to_p75=percentile(all_to, 0.75),
    )
