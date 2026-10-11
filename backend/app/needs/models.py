"""Модель потребности работодателя (PRD §5.1 Need).

ЗП-вилка у потребности — ориентир для матчинга (не обязательна;
обязательная вилка с salary_type — у Invitation и Vacancy, §5.1).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, JSONBVariant, StringArray


class Need(Base):
    __tablename__ = "need"
    __table_args__ = (
        CheckConstraint(
            "salary_from IS NULL OR salary_to IS NULL "
            "OR salary_from <= salary_to",
            name="salary_range",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("company.user_id", ondelete="CASCADE"),
        index=True,
    )
    raw_text: Mapped[str] = mapped_column()
    # распознанная структура «мы поняли так» (LLM-парсинг — core, фаза 2);
    # NULL, пока работодатель правит структуру руками
    parsed: Mapped[dict | None] = mapped_column(JSONBVariant, nullable=True)
    stack_must: Mapped[list] = mapped_column(StringArray, default=list)
    stack_nice: Mapped[list] = mapped_column(StringArray, default=list)
    spec_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    salary_from: Mapped[int | None] = mapped_column(nullable=True)
    salary_to: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
