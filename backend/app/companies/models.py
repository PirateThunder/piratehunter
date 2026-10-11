"""Модель компании-работодателя (PRD §5.1 Company)."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, JSONBVariant


class Company(Base):
    __tablename__ = "company"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(nullable=True)
    industry: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # контакты компании (jsonb): раскрываются кандидату после accept —
    # зеркальное правило §7.2 «контакты раскрываются обеим сторонам»
    contacts: Mapped[dict] = mapped_column(JSONBVariant, default=dict)
    site: Mapped[str | None] = mapped_column(String(500), nullable=True)
