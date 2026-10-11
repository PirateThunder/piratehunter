"""Банк кандидатов (ЛК работодателя, §7.3): вся база с фильтрами —
специализация, грейд (подтверждённый), категория, стек, наличие
достижений ФСП. Карточки — по правилам видимости §7.6 (контакты
скрыты до accept)."""

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..auth.dependencies import EmployerUser
from ..constants import GRADES
from ..database import DbDep
from ..invitations import service as invitations_service
from ..users.models import User
from . import visibility
from .models import CandidateProfile, GradeState
from .schemas import CandidateEmployerOut

router = APIRouter(tags=["employer"])


@router.get(
    "/employer/candidates",
    response_model=list[CandidateEmployerOut],
    summary="Банк кандидатов с фильтрами",
)
async def list_candidates(
    user: EmployerUser,
    session: DbDep,
    spec: str | None = Query(default=None, description="spec_slug"),
    grade: str | None = Query(
        default=None,
        description="подтверждённый грейд; unverified — без подтверждения",
    ),
    stack: str | None = Query(
        default=None, description="технологии через запятую (все обязательны)"
    ),
    fsp: bool | None = Query(
        default=None, description="true — только с историей достижений ФСП"
    ),
    category: str | None = Query(
        default=None,
        description="«spec:grade» — категория §6 (эквивалент spec+grade)",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CandidateEmployerOut]:
    if category:
        spec, _, cat_grade = category.partition(":")
        grade = cat_grade or grade
    if (
        grade is not None
        and grade != "unverified"
        and grade not in GRADES
    ):
        return []  # неизвестный грейд — пустая выдача, а не подмена фильтра

    stmt = (
        select(CandidateProfile, GradeState, User)
        .join(User, User.id == CandidateProfile.user_id)
        .outerjoin(GradeState, GradeState.candidate_id == User.id)
        .order_by(CandidateProfile.updated_at.desc())
    )
    if spec:
        stmt = stmt.where(CandidateProfile.spec_slug == spec)
    if grade == "unverified":
        stmt = stmt.where(GradeState.grade_verified.is_(None))
    elif grade:
        stmt = stmt.where(GradeState.grade_verified == grade)
    rows = (await session.execute(stmt)).all()

    stack_required = (
        [s.strip().lower() for s in stack.split(",") if s.strip()]
        if stack
        else []
    )
    filtered = []
    for profile, grade_state, candidate in rows:
        if stack_required:
            have = {s.lower() for s in profile.stack or []}
            if not all(s in have for s in stack_required):
                continue
        # фильтр «есть достижения ФСП»: история подтянута (не 404)
        if fsp is True and profile.fsp_data is None:
            continue
        if fsp is False and profile.fsp_data is not None:
            continue
        filtered.append((profile, grade_state, candidate))
    page = filtered[offset : offset + limit]

    allowed = await invitations_service.contacts_allowed_ids(
        session, user.id, [p.user_id for p, _, _ in page]
    )
    return [
        visibility.to_employer_view(
            profile, candidate, grade_state,
            contacts_allowed=profile.user_id in allowed,
        )
        for profile, grade_state, candidate in page
    ]
