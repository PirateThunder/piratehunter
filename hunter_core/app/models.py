"""Модели БД ph_core (PRD §5.2).

Отступления от §5.2, зафиксированные сознательно:
- массивы (asked template_ids[], seeds[], stack text[]) и JSONB хранятся как
  sa.JSON — работает и на PG, и на тестовой sqlite;
- у TestSession добавлены служебные поля: mode, pending_template_id/seed
  (текущий открытый вопрос), result (финальный результат, JSON);
- у BetaStat добавлено window (окно ответов для калибровки, JSON).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ItemTemplateModel(Base):
    __tablename__ = "item_template"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    spec_slug: Mapped[str] = mapped_column(String, index=True)
    topic: Mapped[str] = mapped_column(String)
    grade_band: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)  # mcq | sql (code — post-MVP)
    beta: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)  # factory_id + params генератора
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TestSessionModel(Base):
    __tablename__ = "test_session"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String, index=True)
    spec_slug: Mapped[str] = mapped_column(String)
    grade_target: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String, default="full")
    theta: Mapped[float] = mapped_column(Float)
    se: Mapped[float | None] = mapped_column(Float, nullable=True)  # None = inf до ответов
    asked_template_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    seeds: Mapped[list[int]] = mapped_column(JSON, default=list)
    pending_template_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pending_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")  # active | finished
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AnswerModel(Base):
    __tablename__ = "answer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("test_session.id"), index=True)
    template_id: Mapped[str] = mapped_column(String)
    seed: Mapped[int] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(Boolean)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    theta_after: Mapped[float] = mapped_column(Float)


class AssessmentSnapshotModel(Base):
    __tablename__ = "assessment_snapshot"

    candidate_id: Mapped[str] = mapped_column(String, primary_key=True)
    spec_slug: Mapped[str] = mapped_column(String, index=True)
    grade_verified: Mapped[str | None] = mapped_column(String, nullable=True)
    theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    # None = «вычисли сам» — формула theta→score живёт в core (§7.5.2)
    test_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fsp_score: Mapped[float] = mapped_column(Float, default=0.0)
    stack: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BetaStatModel(Base):
    __tablename__ = "beta_stat"

    template_id: Mapped[str] = mapped_column(String, primary_key=True)
    beta: Mapped[float] = mapped_column(Float)
    n_answers: Mapped[int] = mapped_column(Integer, default=0)
    # окно ответов [[theta, correct], ...] до очередной калибровки
    window: Mapped[list[list[float]]] = mapped_column(JSON, default=list)
