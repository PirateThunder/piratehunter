"""Схемы разбора резюме (зафиксированный контракт §8.2+)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ParseResumeIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text не должен быть пустым")
        return v


class ParseResumeOut(BaseModel):
    spec: str | None
    grade_claimed: str | None
    stack: list[str]
    roles: list[str]
    experience_years: int | None = Field(ge=0)
    about: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str
