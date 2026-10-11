"""Ручки профиля компании (ЛК работодателя)."""

from fastapi import APIRouter

from ..auth.dependencies import EmployerUser
from ..database import DbDep
from . import service
from .schemas import CompanyIn, CompanySelfOut

router = APIRouter(tags=["employer"])


@router.get(
    "/employer/company",
    response_model=CompanySelfOut,
    summary="Профиль моей компании",
)
async def get_company(user: EmployerUser, session: DbDep) -> CompanySelfOut:
    """Новый работодатель: пустой профиль компании (200), форма заполнения."""
    company = await service.get_company(session, user.id)
    if company is None:
        return CompanySelfOut(
            company_id=user.id,
            name="",
            description=None,
            industry=None,
            contacts={},
            site=None,
        )
    return service.to_self(company)


@router.put(
    "/employer/company",
    response_model=CompanySelfOut,
    summary="Создать/заменить профиль компании",
)
async def put_company(
    body: CompanyIn, user: EmployerUser, session: DbDep
) -> CompanySelfOut:
    company = await service.upsert_company(session, user, body)
    return service.to_self(company)
