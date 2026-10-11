"""Схемы LLM-парсинга потребности (зафиксированный контракт §8.2+)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ParseNeedIn(BaseModel):
    raw_text: str = Field(min_length=1, max_length=4000)

    @field_validator("raw_text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("raw_text не должен быть пустым")
        return v


class ParseNeedOut(BaseModel):
    spec: str | None
    grade: str | None
    stack_must: list[str]
    stack_nice: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str
