"""Ручки вакансий и откликов (§7.7): кабинет работодателя
(CRUD/publish/close/входящие/PATCH) и кандидатский контур (список
published, отклик, мои отклики).

Видимость: контакты кандидата работодателю — через
invitations.service.contacts_allowed_ids (отклик открывает, §7.6+§7.7);
контакты компании кандидату — только при status=invited (симметрия).
"""

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from ..auth.dependencies import CandidateUser, EmployerUser
from ..candidates import visibility
from ..candidates.models import CandidateProfile, GradeState
from ..companies import service as companies_service
from ..database import DbDep
from ..invitations import service as invitations_service
from ..users.models import User
from . import service
from .constants import APP_INVITED
from .models import Application
from .schemas import (
    ApplicationCandidateOut,
    ApplicationCreatedOut,
    ApplicationEmployerOut,
    ApplicationPatchIn,
    ApplicationVacancyOut,
    ApplyIn,
    VacancyIn,
    VacancyOut,
    VacancyPublicOut,
)

router = APIRouter(tags=["vacancies"])


# --- работодатель: вакансии ---


@router.post(
    "/employer/vacancies",
    response_model=VacancyOut,
    status_code=201,
    summary="Создать вакансию (черновик)",
    description="Вилка ЗП с salary_type обязательна (ТЗ §2.2). "
    "external_id — ATS-идемпотентность: повторный POST с тем же "
    "external_id вернёт 200 и обновит существующую вакансию.",
)
async def create_vacancy(
    body: VacancyIn, user: EmployerUser, session: DbDep, response: Response
) -> VacancyOut:
    await companies_service.get_company_or_404(session, user.id)
    vacancy, created = await service.create_or_update(
        session, user.id, body
    )
    if not created:
        response.status_code = 200
    return VacancyOut.model_validate(vacancy)


@router.get(
    "/employer/vacancies",
    response_model=list[VacancyOut],
    summary="Мои вакансии (все статусы)",
)
async def list_vacancies(user: EmployerUser, session: DbDep) -> list:
    vacancies = await service.list_own(session, user.id)
    return [VacancyOut.model_validate(v) for v in vacancies]


@router.put(
    "/employer/vacancies/{vacancy_id}",
    response_model=VacancyOut,
    summary="Заменить вакансию",
)
async def update_vacancy(
    vacancy_id: str, body: VacancyIn, user: EmployerUser, session: DbDep
) -> VacancyOut:
    vacancy = await service.update(session, user.id, vacancy_id, body)
    return VacancyOut.model_validate(vacancy)


@router.delete(
    "/employer/vacancies/{vacancy_id}",
    status_code=204,
    summary="Удалить вакансию",
)
async def delete_vacancy(
    vacancy_id: str, user: EmployerUser, session: DbDep
) -> None:
    await service.delete(session, user.id, vacancy_id)


@router.post(
    "/employer/vacancies/{vacancy_id}/publish",
    response_model=VacancyOut,
    summary="Опубликовать вакансию",
)
async def publish_vacancy(
    vacancy_id: str, user: EmployerUser, session: DbDep
) -> VacancyOut:
    vacancy = await service.publish(session, user.id, vacancy_id)
    return VacancyOut.model_validate(vacancy)


@router.post(
    "/employer/vacancies/{vacancy_id}/close",
    response_model=VacancyOut,
    summary="Закрыть вакансию",
)
async def close_vacancy(
    vacancy_id: str, user: EmployerUser, session: DbDep
) -> VacancyOut:
    vacancy = await service.close(session, user.id, vacancy_id)
    return VacancyOut.model_validate(vacancy)


# --- работодатель: входящие отклики ---


async def _application_employer_out(
    session, company_id: str, applications: list[Application]
) -> list[ApplicationEmployerOut]:
    candidate_ids = [a.candidate_id for a in applications]
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
    # отклик = кандидат сам инициировал контакт → контакты открыты;
    # решение — единая точка §7.6/§7.7, не ad-hoc
    allowed = await invitations_service.contacts_allowed_ids(
        session, company_id, candidate_ids
    )
    out = []
    for application in applications:
        cid = application.candidate_id
        profile, candidate = profiles.get(cid), users.get(cid)
        if profile is None or candidate is None:
            continue
        out.append(
            ApplicationEmployerOut(
                id=application.id,
                status=application.status,
                message=application.message,
                created_at=application.created_at,
                candidate=visibility.to_employer_view(
                    profile,
                    candidate,
                    grade_states.get(cid),
                    contacts_allowed=cid in allowed,
                ),
            )
        )
    return out


@router.get(
    "/employer/vacancies/{vacancy_id}/applications",
    response_model=list[ApplicationEmployerOut],
    summary="Входящие отклики на вакансию",
    description="Первый GET переводит sent → viewed (как у приглашений). "
    "Контакты кандидата видны — отклик = кандидат сам инициировал "
    "контакт (§7.7).",
)
async def list_applications(
    vacancy_id: str, user: EmployerUser, session: DbDep
) -> list[ApplicationEmployerOut]:
    applications = await service.list_for_employer(
        session, user.id, vacancy_id
    )
    return await _application_employer_out(session, user.id, applications)


@router.patch(
    "/employer/applications/{application_id}",
    response_model=ApplicationEmployerOut,
    summary="Сменить статус отклика",
)
async def patch_application(
    application_id: str,
    body: ApplicationPatchIn,
    user: EmployerUser,
    session: DbDep,
) -> ApplicationEmployerOut:
    application = await service.patch_status(
        session, user.id, application_id, body.status
    )
    out = await _application_employer_out(session, user.id, [application])
    return out[0]


# --- кандидат: список вакансий и отклики ---


@router.get(
    "/vacancies",
    response_model=list[VacancyPublicOut],
    summary="Опубликованные вакансии (фильтры)",
)
async def list_public_vacancies(
    user: CandidateUser,
    session: DbDep,
    spec: str | None = Query(default=None),
    grade: str | None = Query(default=None),
    stack: str | None = Query(
        default=None, description="через запятую, все обязательны"
    ),
    salary_from: int | None = Query(
        default=None, ge=0, description="желаемая ЗП — вилка вакансии "
        "должна достигать её"
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[VacancyPublicOut]:
    stack_list = (
        [s.strip() for s in stack.split(",") if s.strip()] if stack else []
    )
    rows = await service.list_public(
        session,
        user.id,
        spec=spec,
        grade=grade,
        stack=stack_list,
        salary_from=salary_from,
        limit=limit,
        offset=offset,
    )
    return [
        VacancyPublicOut(
            id=v.id,
            title=v.title,
            description=v.description,
            spec_slug=v.spec_slug,
            grade=v.grade,
            stack_must=list(v.stack_must or []),
            stack_nice=list(v.stack_nice or []),
            salary_from=v.salary_from,
            salary_to=v.salary_to,
            salary_type=v.salary_type,
            company={
                "name": c.name,
                "industry": c.industry,
                "site": c.site,
            },
            published_at=v.published_at,
            already_applied=applied,
        )
        for v, c, applied in rows
    ]


@router.post(
    "/vacancies/{vacancy_id}/apply",
    response_model=ApplicationCreatedOut,
    status_code=201,
    summary="Откликнуться на вакансию",
    description="404 — вакансия не published; 409 — повторный отклик.",
)
async def apply(
    vacancy_id: str, user: CandidateUser, session: DbDep, body: ApplyIn | None = None
) -> ApplicationCreatedOut:
    if await session.get(CandidateProfile, user.id) is None:
        raise HTTPException(422, "сначала заполните профиль")
    application = await service.apply(
        session, user, vacancy_id, body.message if body else None
    )
    return ApplicationCreatedOut.model_validate(application)


@router.get(
    "/candidate/applications",
    response_model=list[ApplicationCandidateOut],
    summary="Мои отклики",
    description="Контакты компании раскрыты только при status=invited "
    "(симметрия §7.6).",
)
async def my_applications(
    user: CandidateUser, session: DbDep
) -> list[ApplicationCandidateOut]:
    rows = await service.list_for_candidate(session, user.id)
    return [
        ApplicationCandidateOut(
            id=application.id,
            status=application.status,
            message=application.message,
            created_at=application.created_at,
            vacancy=ApplicationVacancyOut.model_validate(vacancy),
            company=companies_service.to_candidate_view(
                company,
                contacts_allowed=application.status == APP_INVITED,
            ),
        )
        for application, vacancy, company in rows
    ]
