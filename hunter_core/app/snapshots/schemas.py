"""Схемы снапшотов (PRD §4.3)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SnapshotIn(BaseModel):
    spec: str = Field(min_length=1)
    grade_verified: str | None = None
    theta: float | None = Field(default=None, ge=-4.0, le=4.0)
    # None — core вычислит сам из theta/grade (§7.5.2)
    test_score: float | None = Field(default=None, ge=0.0, le=1.0)
    fsp_score: float = Field(default=0.0, ge=0.0, le=1.0)
    stack: list[str] = Field(default_factory=list)


class SnapshotOut(SnapshotIn):
    candidate_id: str
    updated_at: datetime
