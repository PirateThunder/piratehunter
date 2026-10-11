"""Модели вакансий и откликов (PRD §5.1 Vacancy/Application, §7.7).

Вилка ЗП обязательна и с salary_type (инвариант ТЗ §2.2, как у
Invitation). external_id — для ATS-идемпотентности (§17): уникален в
рамках компании, повторный POST с тем же external_id обновляет
вакансию (200) вместо создания дубля.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, JSONBVariant, utcnow
from .constants import APP_SENT, APP_STATUSES, VACANCY_DRAFT, VACANCY_STATUSES


class Vacancy(Base):
    __tablename__ = "vacancy"
    __table_args__ = (
        CheckConstraint("salary_from > 0", name="salary_from_positive"),
        CheckConstraint("salary_from <= salary_to", name="salary_range"),
        CheckConstraint(
            "salary_type IN ('gross', 'net')", name="salary_type"
        ),
        CheckConstraint(
            "status IN ("
            + ", ".join(f"'{s}'" for s in VACANCY_STATUSES)
            + ")",
            name="status",
        ),
        UniqueConstraint("company_id", "external_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("company.user_id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column()
    spec_slug: Mapped[str] = mapped_column(String(64))
    grade: Mapped[str] = mapped_column(String(16))
    stack_must: Mapped[list] = mapped_column(JSONBVariant, default=list)
    stack_nice: Mapped[list] = mapped_column(JSONBVariant, default=list)
    salary_from: Mapped[int] = mapped_column()
    salary_to: Mapped[int] = mapped_column()
    salary_type: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default=VACANCY_DRAFT)
    # ATS-идемпотентность (§17): внешний id из системы работодателя
    external_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Application(Base):
    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "candidate_id"),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in APP_STATUSES) + ")",
            name="status",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    vacancy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vacancy.id", ondelete="CASCADE"),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    message: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=APP_SENT)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow
    )
