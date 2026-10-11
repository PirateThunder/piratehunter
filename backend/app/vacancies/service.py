"""Логика вакансий и откликов (§7.7). Видимость контактов — только
через invitations.service.contacts_allowed_ids (§7.6 + отклики)."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from ..companies.models import Company
from ..constants import GRADES, SPECIALIZATIONS
from ..users.models import User
from .constants import (
    APP_SENT,
    APP_VIEWED,
    VACANCY_CLOSED,
    VACANCY_PUBLISHED,
)
from .models import Application, Vacancy
from .schemas import VacancyIn


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _validate_catalog(spec_slug: str, grade: str) -> None:
    if spec_slug not in SPECIALIZATIONS:
        raise HTTPException(
            422, f"неизвестная специализация: {spec_slug}"
        )
    if grade not in GRADES:
        raise HTTPException(422, f"неизвестный грейд: {grade}")


# --- работодатель: вакансии ---


async def create_or_update(
    session: AsyncSession, company_id: str, body: VacancyIn
) -> tuple[Vacancy, bool]:
    """Создание; при совпадении external_id — обновление существующей
    (ATS-идемпотентность, §17). → (vacancy, created)."""
    _validate_catalog(body.spec_slug, body.grade)
    if body.external_id:
        existing = await session.scalar(
            select(Vacancy).where(
                Vacancy.company_id == company_id,
                Vacancy.external_id == body.external_id,
            )
        )
        if existing is not None:
            data = body.model_dump()
            for field, value in data.items():
                setattr(existing, field, value)
            await session.commit()
            return existing, False
    vacancy = Vacancy(company_id=company_id, **body.model_dump())
    session.add(vacancy)
    await session.commit()
    return vacancy, True


async def list_own(session: AsyncSession, company_id: str) -> list[Vacancy]:
    result = await session.scalars(
        select(Vacancy)
        .where(Vacancy.company_id == company_id)
        .order_by(Vacancy.created_at.desc())
    )
    return list(result)


async def get_own(
    session: AsyncSession, company_id: str, vacancy_id: str
) -> Vacancy:
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.company_id != company_id:
        raise HTTPException(404, "вакансия не найдена")
    return vacancy


async def update(
    session: AsyncSession, company_id: str, vacancy_id: str, body: VacancyIn
) -> Vacancy:
    _validate_catalog(body.spec_slug, body.grade)
    vacancy = await get_own(session, company_id, vacancy_id)
    for field, value in body.model_dump().items():
        setattr(vacancy, field, value)
    await session.commit()
    return vacancy


async def delete(
    session: AsyncSession, company_id: str, vacancy_id: str
) -> None:
    vacancy = await get_own(session, company_id, vacancy_id)
    await session.delete(vacancy)
    await session.commit()


async def publish(
    session: AsyncSession, company_id: str, vacancy_id: str
) -> Vacancy:
    """draft|closed → published (published_at=now)."""
    vacancy = await get_own(session, company_id, vacancy_id)
    if vacancy.status == VACANCY_PUBLISHED:
        raise HTTPException(409, "вакансия уже опубликована")
    vacancy.status = VACANCY_PUBLISHED
    vacancy.published_at = _now()
    vacancy.closed_at = None
    await session.commit()
    return vacancy


async def close(
    session: AsyncSession, company_id: str, vacancy_id: str
) -> Vacancy:
    """draft|published → closed (closed_at=now)."""
    vacancy = await get_own(session, company_id, vacancy_id)
    if vacancy.status == VACANCY_CLOSED:
        raise HTTPException(409, "вакансия уже закрыта")
    vacancy.status = VACANCY_CLOSED
    vacancy.closed_at = _now()
    await session.commit()
    return vacancy


# --- отклики ---


async def apply(
    session: AsyncSession,
    candidate: User,
    vacancy_id: str,
    message: str | None,
) -> Application:
    """Отклик кандидата: 404 если вакансия не published, 409 при
    повторе (UNIQUE vacancy_id+candidate_id — и в БД)."""
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None or vacancy.status != VACANCY_PUBLISHED:
        raise HTTPException(404, "вакансия не найдена или не опубликована")
    existing = await session.scalar(
        select(Application).where(
            Application.vacancy_id == vacancy_id,
            Application.candidate_id == candidate.id,
        )
    )
    if existing is not None:
        raise HTTPException(409, "вы уже откликались на эту вакансию")
    application = Application(
        vacancy_id=vacancy_id, candidate_id=candidate.id, message=message
    )
    session.add(application)
    await session.commit()
    return application


async def list_for_employer(
    session: AsyncSession, company_id: str, vacancy_id: str
) -> list[Application]:
    """Входящие отклики на свою вакансию. Первый GET переводит
    sent → viewed (как у приглашений, §7.6)."""
    await get_own(session, company_id, vacancy_id)
    await session.execute(
        sa_update(Application)
        .where(
            Application.vacancy_id == vacancy_id,
            Application.status == APP_SENT,
        )
        .values(status=APP_VIEWED)
    )
    result = await session.scalars(
        select(Application)
        .where(Application.vacancy_id == vacancy_id)
        .order_by(Application.created_at.desc())
    )
    applications = list(result)
    await session.commit()
    return applications


async def patch_status(
    session: AsyncSession, company_id: str, application_id: str, status: str
) -> Application:
    """Смена статуса отклика (viewed|invited|rejected) — только на
    вакансии своей компании (чужие → 404)."""
    application = await session.get(Application, application_id)
    if application is None:
        raise HTTPException(404, "отклик не найден")
    vacancy = await session.get(Vacancy, application.vacancy_id)
    if vacancy is None or vacancy.company_id != company_id:
        raise HTTPException(404, "отклик не найден")
    application.status = status
    await session.commit()
    return application


async def list_for_candidate(
    session: AsyncSession, candidate_id: str
) -> list[tuple[Application, Vacancy, Company]]:
    rows = (
        await session.execute(
            select(Application, Vacancy, Company)
            .join(Vacancy, Vacancy.id == Application.vacancy_id)
            .join(Company, Company.user_id == Vacancy.company_id)
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.created_at.desc())
        )
    ).all()
    return [(app, vacancy, company) for app, vacancy, company in rows]


# --- кандидат: публичный список вакансий ---


async def list_public(
    session: AsyncSession,
    candidate_id: str,
    *,
    spec: str | None,
    grade: str | None,
    stack: list[str],
    salary_from: int | None,
    limit: int,
    offset: int,
) -> list[tuple[Vacancy, Company, bool]]:
    """Опубликованные вакансии с фильтрами (spec/grade/stack-all/
    «вилка достаёт до salary_from») + флаг already_applied."""
    stmt = (
        select(Vacancy, Company)
        .join(Company, Company.user_id == Vacancy.company_id)
        .where(Vacancy.status == VACANCY_PUBLISHED)
        .order_by(Vacancy.published_at.desc())
    )
    if spec:
        stmt = stmt.where(Vacancy.spec_slug == spec)
    if grade:
        stmt = stmt.where(Vacancy.grade == grade)
    if salary_from is not None:
        # желаемая сумма должна укладываться в вилку вакансии сверху
        stmt = stmt.where(Vacancy.salary_to >= salary_from)
    rows = (await session.execute(stmt)).all()

    stack_required = [s.lower() for s in stack]
    my_applications = set(
        await session.scalars(
            select(Application.vacancy_id).where(
                Application.candidate_id == candidate_id
            )
        )
    )
    filtered = []
    for vacancy, company in rows:
        if stack_required:
            have = {s.lower() for s in (vacancy.stack_must or [])}
            have |= {s.lower() for s in (vacancy.stack_nice or [])}
            if not all(s in have for s in stack_required):
                continue
        filtered.append(
            (vacancy, company, vacancy.id in my_applications)
        )
    return filtered[offset : offset + limit]
