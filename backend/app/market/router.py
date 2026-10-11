"""Виджет «вилка vs рынок по категории» (PRD §7.5.5) — экраны
потребности/приглашения/вакансии работодателя."""

from fastapi import APIRouter, HTTPException, Query

from ..auth.dependencies import EmployerUser
from ..constants import GRADES, SPECIALIZATIONS
from ..core_client.client import CoreDep
from ..database import DbDep
from . import service
from .schemas import SalaryStatsOut

router = APIRouter(tags=["employer"])


@router.get(
    "/employer/market/salary",
    response_model=SalaryStatsOut,
    summary="Рыночная аналитика вилок по категории",
    description="Медиана и квартили ЗП-вилок категории spec×grade по "
    "данным платформы (потребности + приглашения, анонимно) + размер "
    "категории из core. Пустая выборка → перцентили null, 200.",
)
async def market_salary(
    user: EmployerUser,
    session: DbDep,
    core: CoreDep,
    spec: str = Query(description="специализация из справочника §6"),
    grade: str = Query(description="грейд из справочника §6"),
) -> SalaryStatsOut:
    if spec not in SPECIALIZATIONS:
        raise HTTPException(
            422, f"неизвестная специализация; доступны: {list(SPECIALIZATIONS)}"
        )
    if grade not in GRADES:
        raise HTTPException(
            422, f"неизвестный грейд; доступны: {list(GRADES)}"
        )
    return await service.salary_stats(session, core, spec, grade)
