"""Логика компании: upsert профиля, сериализация public/contacts."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..users.models import User
from .models import Company
from .schemas import (
    CompanyCandidateOut,
    CompanyContactsOut,
    CompanyIn,
    CompanyPublicOut,
    CompanySelfOut,
)


async def get_company(
    session: AsyncSession, user_id: str
) -> Company | None:
    return await session.get(Company, user_id)


async def get_company_or_404(
    session: AsyncSession, user_id: str
) -> Company:
    company = await get_company(session, user_id)
    if company is None:
        raise HTTPException(404, "профиль компании не заполнен")
    return company


async def upsert_company(
    session: AsyncSession, user: User, body: CompanyIn
) -> Company:
    company = await session.get(Company, user.id)
    if company is None:
        company = Company(user_id=user.id, name=body.name)
        session.add(company)
    for field in ("name", "description", "industry", "contacts", "site"):
        setattr(company, field, getattr(body, field))
    await session.commit()
    return company


def to_self(company: Company) -> CompanySelfOut:
    return CompanySelfOut(
        company_id=company.user_id,
        name=company.name,
        description=company.description,
        industry=company.industry,
        contacts=company.contacts or {},
        site=company.site,
    )


def to_candidate_view(
    company: Company, *, contacts_allowed: bool
) -> CompanyCandidateOut:
    """Компания в приглашении кандидата: contacts — только после
    accept (зеркальное правило видимости, §7.2)."""
    return CompanyCandidateOut(
        company=CompanyPublicOut(
            company_id=company.user_id,
            name=company.name,
            description=company.description,
            industry=company.industry,
            site=company.site,
        ),
        contacts=(
            CompanyContactsOut(contacts=company.contacts or {})
            if contacts_allowed
            else None
        ),
    )
