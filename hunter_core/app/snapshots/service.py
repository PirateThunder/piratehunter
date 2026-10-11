"""Сервис снапшотов: upsert от backend (пуш после изменений профиля/теста)."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestError, NotFoundError
from app.models import AssessmentSnapshotModel, utcnow
from app.snapshots.schemas import SnapshotIn
from engine.catalog import get_grade, get_specialization


async def upsert_snapshot(
    db: AsyncSession, candidate_id: str, payload: SnapshotIn
) -> AssessmentSnapshotModel:
    try:
        get_specialization(payload.spec)
        if payload.grade_verified is not None:
            get_grade(payload.grade_verified)
    except ValueError as e:
        raise BadRequestError(str(e)) from e
    row = await db.get(AssessmentSnapshotModel, candidate_id)
    if row is None:
        row = AssessmentSnapshotModel(candidate_id=candidate_id, spec_slug=payload.spec)
    row.spec_slug = payload.spec
    row.grade_verified = payload.grade_verified
    row.theta = payload.theta
    row.test_score = payload.test_score
    row.fsp_score = payload.fsp_score
    row.stack = payload.stack
    row.updated_at = utcnow()
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_snapshot(db: AsyncSession, candidate_id: str) -> AssessmentSnapshotModel:
    row = await db.get(AssessmentSnapshotModel, candidate_id)
    if row is None:
        raise NotFoundError(f"снапшот кандидата {candidate_id!r} не найден")
    return row


async def delete_all_snapshots(db: AsyncSession) -> None:
    """Полная очистка таблицы снапшотов (и только её) — ресид демо-стенда §10."""
    await db.execute(delete(AssessmentSnapshotModel))
    await db.commit()
