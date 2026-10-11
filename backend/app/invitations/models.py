"""Модель приглашения (PRD §5.1 Invitation).

Инвариант ТЗ §2.2: вилка ЗП обязательна — salary_from/salary_to NOT
NULL, from ≤ to, salary_type: gross|net обязателен (Q&A 06.10:
гросс/нетто непринципиально, лишь бы явно). Привязка к вакансии
(vacancy_id) — фаза 2 (вакансии опциональны, §7.7), колонка появится
вместе с моделью Vacancy.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base
from .constants import STATUSES


class Invitation(Base):
    __tablename__ = "invitation"
    __table_args__ = (
        CheckConstraint("salary_from > 0", name="salary_from_positive"),
        CheckConstraint("salary_from <= salary_to", name="salary_range"),
        CheckConstraint(
            "salary_type IN ('gross', 'net')", name="salary_type"
        ),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in STATUSES) + ")",
            name="status",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("company.user_id", ondelete="CASCADE"),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column()
    salary_from: Mapped[int] = mapped_column()
    salary_to: Mapped[int] = mapped_column()
    salary_type: Mapped[str] = mapped_column(String(8))
    contact_method: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="sent")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    status_at: Mapped[datetime] = mapped_column(server_default=func.now())
