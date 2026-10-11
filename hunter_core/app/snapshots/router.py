"""Роутер снапшотов (контракт §8.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.snapshots import service
from app.snapshots.schemas import SnapshotIn, SnapshotOut

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.put(
    "/{candidate_id}",
    response_model=SnapshotOut,
    status_code=status.HTTP_200_OK,
    summary="Пуш оценочного снапшота от backend (upsert)",
)
async def put_snapshot(
    candidate_id: str,
    payload: SnapshotIn,
    db: DbDep,
) -> SnapshotOut:
    row = await service.upsert_snapshot(db, candidate_id, payload)
    return SnapshotOut(
        candidate_id=row.candidate_id,
        spec=row.spec_slug,
        grade_verified=row.grade_verified,
        theta=row.theta,
        test_score=row.test_score,
        fsp_score=row.fsp_score,
        stack=row.stack,
        updated_at=row.updated_at,
    )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Полная очистка таблицы снапшотов (ресид демо-стенда, PRD §10); "
    "идемпотентно",
)
async def delete_snapshots(db: DbDep) -> Response:
    await service.delete_all_snapshots(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
