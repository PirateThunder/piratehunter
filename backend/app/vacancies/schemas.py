"""Схемы вакансий и откликов (§7.7). Вилка ЗП обязательна, как у
приглашений (инвариант ТЗ §2.2)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..candidates.schemas import CandidateEmployerOut
from ..companies.schemas import CompanyCandidateOut
from ..constants import GRADES

SLUG_RE = r"^[a-z0-9][a-z0-9-]{0,63}$"


class VacancyIn(BaseModel):
    """Создание/правка вакансии. external_id — id внешней ATS:
    повторный POST с тем же external_id обновляет существующую
    вакансию (идемпотентность, §17)."""

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=20000)
    spec_slug: str = Field(pattern=SLUG_RE)
    grade: Literal[*GRADES]
    stack_must: list[str] = Field(default_factory=list, max_length=64)
    stack_nice: list[str] = Field(default_factory=list, max_length=64)
    salary_from: int = Field(gt=0)
    salary_to: int = Field(gt=0)
    salary_type: Literal["gross", "net"]
    external_id: str | None = Field(default=None, max_length=128)

    @field_validator("stack_must", "stack_nice")
    @classmethod
    def _strip_items(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s.strip()][:64]

    @model_validator(mode="after")
    def _salary_range(self):
        if self.salary_from > self.salary_to:
            raise ValueError("salary_from не может быть больше salary_to")
        return self


class VacancyOut(BaseModel):
    """Вакансия в кабинете работодателя (все статусы)."""

    id: str
    company_id: str
    title: str
    description: str
    spec_slug: str
    grade: str
    stack_must: list
    stack_nice: list
    salary_from: int
    salary_to: int
    salary_type: str
    status: str
    external_id: str | None
    created_at: datetime
    published_at: datetime | None
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class VacancyCompanyOut(BaseModel):
    """Компания в публичной карточке вакансии (контакты не входят)."""

    name: str
    industry: str | None
    site: str | None


class VacancyPublicOut(BaseModel):
    """Публичная вакансия (кандидатский список, только published)."""

    id: str
    title: str
    description: str
    spec_slug: str
    grade: str
    stack_must: list
    stack_nice: list
    salary_from: int
    salary_to: int
    salary_type: str
    company: VacancyCompanyOut
    published_at: datetime | None
    already_applied: bool = False


class ApplyIn(BaseModel):
    message: str | None = Field(default=None, max_length=10000)


class ApplicationVacancyOut(BaseModel):
    id: str
    title: str
    salary_from: int
    salary_to: int
    salary_type: str

    model_config = {"from_attributes": True}


class ApplicationCandidateOut(BaseModel):
    """Мой отклик (кабинет кандидата): контакты компании раскрыты
    только при status=invited (симметрия §7.6)."""

    id: str
    status: str
    message: str | None
    created_at: datetime
    vacancy: ApplicationVacancyOut
    company: CompanyCandidateOut


class ApplicationEmployerOut(BaseModel):
    """Входящий отклик (кабинет работодателя): контакты кандидата
    видны — он сам инициировал контакт (§7.7)."""

    id: str
    status: str
    message: str | None
    created_at: datetime
    candidate: CandidateEmployerOut


class ApplicationPatchIn(BaseModel):
    status: Literal["viewed", "invited", "rejected"]


class ApplicationCreatedOut(BaseModel):
    """Ответ apply: 201."""

    id: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
