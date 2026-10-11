"""Модели кандидата: CandidateProfile и GradeState (PRD §5.1).

Отличия от букв §5.1 (зафиксированы в отчёте):
- fsp_id живёт на User (auth-идентичность, §7.1), сюда не дублируется;
- consent_pd/consent_publish — на User (согласия дают обе роли §7.1);
- +fsp_score/+fsp_data — денормализованный снапшот достижений ФСП,
  чтобы банк кандидатов и подборка не дёргали fsp_registry на каждую
  карточку (фильтр «есть достижения» §7.3, NFR производительность §12).
"""

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, JSONBVariant, StringArray, utcnow


class CandidateProfile(Base):
    __tablename__ = "candidate_profile"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    fio: Mapped[str] = mapped_column(String(300))
    # контакты — скрыты до accept приглашения (§7.6): phone, ссылки в
    # contacts jsonb, email — на User
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contacts: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
    stack: Mapped[list] = mapped_column(StringArray, default=list)
    spec_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    grade_claimed: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    experience_years: Mapped[int | None] = mapped_column(nullable=True)
    roles: Mapped[list] = mapped_column(StringArray, default=list)
    soft_skills: Mapped[list] = mapped_column(StringArray, default=list)
    about: Mapped[str | None] = mapped_column(nullable=True)
    resume_text: Mapped[str | None] = mapped_column(nullable=True)
    # {anonymous: bool, show_fsp: bool, show_stack: bool} — настройки
    # приватности §7.2 (анонимный режим «Кандидат #id» — опция кандидата)
    privacy: Mapped[dict] = mapped_column(
        JSONBVariant,
        default=lambda: {
            "anonymous": False,
            "show_fsp": True,
            "show_stack": True,
        },
    )
    # денормализованные достижения ФСП (обновляются при привязке FSP ID /
    # входе через FSP ID): последний ответ реестра (None = нет истории)
    fsp_score: Mapped[float] = mapped_column(default=0.0)
    fsp_data: Mapped[dict | None] = mapped_column(JSONBVariant, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow
    )


class GradeState(Base):
    """Статус грейда кандидата (§5.1). Кулдауны считаются от
    grade_changed_at / last_test_at (§7.4.3)."""

    __tablename__ = "grade_state"

    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    grade_verified: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    theta: Mapped[float | None] = mapped_column(nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(nullable=True)
    grade_changed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # unverified|confirmed|upgrade_offer|downgrade_offer
    status: Mapped[str] = mapped_column(String(32), default="unverified")
