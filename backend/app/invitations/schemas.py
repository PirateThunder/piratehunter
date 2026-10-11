"""Схемы приглашений. Вилка ЗП с salary_type обязательна и видна
кандидату ДО ответа (ТЗ §2.2.1 — принципиальное отличие сервиса)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..candidates.schemas import CandidateEmployerOut
from ..companies.schemas import CompanyCandidateOut


class InvitationCreateIn(BaseModel):
    """POST /employer/invitations: текст + обязательная вилка ЗП +
    способ связи. Валидация на уровне схемы (и БД, §7.6)."""

    candidate_id: str = Field(min_length=1, max_length=36)
    text: str = Field(min_length=1, max_length=10000)
    salary_from: int = Field(gt=0, description="рублей, обязательна")
    salary_to: int = Field(gt=0)
    salary_type: Literal["gross", "net"]
    contact_method: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def _salary_range(self):
        if self.salary_from > self.salary_to:
            raise ValueError("salary_from не может быть больше salary_to")
        return self


class InvitationBaseOut(BaseModel):
    id: str
    text: str
    salary_from: int
    salary_to: int
    salary_type: str
    contact_method: str
    status: str
    created_at: datetime
    status_at: datetime

    model_config = {"from_attributes": True}


class InvitationCandidateOut(InvitationBaseOut):
    """Входящее у кандидата: компания (контакты — после accept)."""

    company: CompanyCandidateOut


class InvitationEmployerOut(InvitationBaseOut):
    """Исходящее у работодателя: кандидат (контакты — после accept)."""

    candidate: CandidateEmployerOut


class InvitationAcceptOut(BaseModel):
    """Ответ на accept: раскрытые контакты ОБЕИХ сторон (§7.2)."""

    invitation: InvitationCandidateOut
