"""Схемы потребностей и подборки (shortlist с explanation, §7.5.3)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..candidates.schemas import CandidateEmployerOut
from ..constants import GRADES

SLUG_RE = r"^[a-z0-9][a-z0-9-]{0,63}$"


class NeedIn(BaseModel):
    """Создание/замена потребности: свободный текст + структура."""

    raw_text: str = Field(min_length=1, max_length=20000)
    stack_must: list[str] = Field(default_factory=list, max_length=64)
    stack_nice: list[str] = Field(default_factory=list, max_length=64)
    spec_slug: str | None = Field(default=None, pattern=SLUG_RE)
    grade: Literal[*GRADES] | None = None
    salary_from: int | None = Field(default=None, ge=0)
    salary_to: int | None = Field(default=None, ge=0)

    @field_validator("stack_must", "stack_nice")
    @classmethod
    def _strip_items(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s.strip()][:64]

    @model_validator(mode="after")
    def _salary_range(self):
        if (
            self.salary_from is not None
            and self.salary_to is not None
            and self.salary_from > self.salary_to
        ):
            raise ValueError("salary_from не может быть больше salary_to")
        return self


class NeedParseIn(BaseModel):
    """POST /employer/needs/parse: свободный текст потребности для
    LLM-разбора («мы поняли так», §7.3)."""

    raw_text: str = Field(min_length=1, max_length=20000)


class NeedParseOut(BaseModel):
    """Распознанная структура потребности — прокси ответа core
    POST /internal/llm/parse-need (контракт фазы 2)."""

    spec: str | None
    grade: str | None
    stack_must: list[str]
    stack_nice: list[str]
    confidence: float
    notes: str


class NeedOut(BaseModel):
    id: str
    company_id: str
    raw_text: str
    parsed: dict | None
    stack_must: list[str]
    stack_nice: list[str]
    spec_slug: str | None
    grade: str | None
    salary_from: int | None
    salary_to: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShortlistItemOut(BaseModel):
    """Строка подборки: карточка кандидата (видимость §7.6) + score и
    панель «Почему в подборке» от core (§7.5.3)."""

    candidate: CandidateEmployerOut
    score: float
    explanation: Any  # структура факторов ядра — проксируем как есть


class ShortlistOut(BaseModel):
    need_id: str
    results: list[ShortlistItemOut]
