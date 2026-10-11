"""Кандидатские ручки: профиль, привязка ФСП ID, статус грейда.

Резюме PDF (разбор §7.10 и генерация профиля) — фаза 3 по PRD §14,
здесь не реализовано (зафиксировано в отчёте).
"""

from fastapi import APIRouter

from ..auth.dependencies import CandidateUser
from ..core_client.client import CoreDep, CoreError
from ..database import DbDep
from ..fsp.client import FspDep
from ..redis import RedisDep
from . import service, visibility
from .schemas import CandidateSelfOut, FspLinkIn, GradeOut, ProfileIn

router = APIRouter(tags=["candidate"])


@router.get(
    "/candidate/profile",
    response_model=CandidateSelfOut,
    summary="Мой профиль (полный, с контактами)",
)
async def get_profile(user: CandidateUser, session: DbDep) -> CandidateSelfOut:
    """Нового пользователя (вход через FSP ID/email) профиля ещё нет —
    отдаём 200 с пустым черновиком: клиенты показывают форму заполнения,
    а не зависают на 404."""
    profile = await service.get_profile(session, user.id)
    if profile is None:
        return visibility.empty_self(user)
    grade_state = await service.get_grade_state(session, user.id)
    return visibility.to_self(profile, user, grade_state)


@router.put(
    "/candidate/profile",
    response_model=CandidateSelfOut,
    summary="Создать/заменить профиль",
)
async def put_profile(
    body: ProfileIn, user: CandidateUser, session: DbDep, core: CoreDep
) -> CandidateSelfOut:
    profile = await service.upsert_profile(session, user, body)
    grade_state = await service.get_grade_state(session, user.id)
    await service.try_push_snapshot(core, profile, grade_state)
    return visibility.to_self(profile, user, grade_state)


@router.post(
    "/candidate/fsp-link",
    response_model=CandidateSelfOut,
    summary="Привязать ФСП ID",
)
async def link_fsp(
    body: FspLinkIn,
    user: CandidateUser,
    session: DbDep,
    redis: RedisDep,
    core: CoreDep,
    fsp: FspDep,
) -> CandidateSelfOut:
    """Привязка ФСП ID в настройках: достижения забираются сразу
    (404 реестра = «нет истории» → score 0, блок не рендерится)."""
    profile = await service.link_fsp(
        session, core, fsp, redis, user, body.fsp_id
    )
    grade_state = await service.get_grade_state(session, user.id)
    return visibility.to_self(profile, user, grade_state)


@router.delete(
    "/candidate/fsp-link",
    response_model=CandidateSelfOut,
    summary="Отвязать ФСП ID",
)
async def unlink_fsp(
    user: CandidateUser, session: DbDep, core: CoreDep
) -> CandidateSelfOut:
    profile = await service.unlink_fsp(session, core, user)
    grade_state = await service.get_grade_state(session, user.id)
    return visibility.to_self(profile, user, grade_state)


@router.get(
    "/candidate/grade",
    response_model=GradeOut,
    summary="Статус грейда: история, кулдауны, место в категории",
)
async def get_grade(
    user: CandidateUser, session: DbDep, core: CoreDep
) -> GradeOut:
    profile = await service.get_profile(session, user.id)
    if profile is None:
        # новый пользователь: грейда нет — «не подтверждён», без 404
        return GradeOut(
            spec_slug=None,
            grade_claimed=None,
            grade_verified=None,
            status="unverified",
            theta=None,
            last_test_at=None,
            grade_changed_at=None,
            retest_available_at=None,
            change_available_at=None,
            category_rank=None,
            category_size=None,
        )
    grade_state = await service.get_grade_state(session, user.id)
    retest_at, change_at = service.cooldown_dates(grade_state)
    rank = size = None
    if (
        grade_state is not None
        and grade_state.grade_verified
        and profile.spec_slug
    ):
        try:
            ranking = await core.category_ranking(
                profile.spec_slug, grade_state.grade_verified
            )
            size = len(ranking)
            for idx, row in enumerate(ranking, start=1):
                if row.get("candidate_id") == user.id:
                    rank = idx
                    break
        except CoreError:
            pass  # core недоступен — статус грейда покажем без места
    return GradeOut(
        spec_slug=profile.spec_slug,
        grade_claimed=profile.grade_claimed,
        grade_verified=grade_state.grade_verified if grade_state else None,
        status=grade_state.status if grade_state else "unverified",
        theta=grade_state.theta if grade_state else None,
        last_test_at=grade_state.last_test_at if grade_state else None,
        grade_changed_at=(
            grade_state.grade_changed_at if grade_state else None
        ),
        retest_available_at=retest_at,
        change_available_at=change_at,
        category_rank=rank,
        category_size=size,
    )
