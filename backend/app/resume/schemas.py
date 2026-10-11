"""Схемы резюме-контура (§7.10)."""

from pydantic import BaseModel, Field


class ResumeDraft(BaseModel):
    """Черновик профиля — контракт core POST /internal/llm/parse-resume.
    Пустой (core недоступен) → все поля пустые, notes объясняет."""

    spec: str | None = None
    grade_claimed: str | None = None
    stack: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    about: str | None = None
    confidence: float = 0.0
    notes: str = ""


class ResumeDraftOut(BaseModel):
    """POST /candidate/profile/resume → {draft}: разобранный черновик
    для ручного review на фронте. Профиль НЕ перезаписывается."""

    draft: ResumeDraft = Field(default_factory=ResumeDraft)
