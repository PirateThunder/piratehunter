"""Роутер матчинга (контракт §8.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.matching import service
from app.matching.schemas import MatchItemOut, NeedIn

router = APIRouter(tags=["matching"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/match",
    response_model=list[MatchItemOut],
    summary="Подборка по потребности: ranked кандидаты с explanation",
)
async def match_candidates(
    payload: NeedIn,
    db: DbDep,
) -> list[dict]:
    snapshots = await service.list_snapshots(db, spec=payload.spec)
    return await run_in_threadpool(
        service.rank_match_sync, snapshots, payload.model_dump()
    )


@router.get(
    "/category/{spec}/{grade}/ranking",
    response_model=list[MatchItemOut],
    summary="Ранжированная категория spec × grade (PRD §7.5.4)",
)
async def category_ranking(
    spec: str,
    grade: str,
    db: DbDep,
) -> list[dict]:
    snapshots = await service.list_snapshots(db, spec=spec)
    return await run_in_threadpool(service.rank_category_sync, snapshots, spec, grade)
