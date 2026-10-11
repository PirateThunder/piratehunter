"""Схемы матчинга (контракт §8.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NeedIn(BaseModel):
    spec: str = Field(min_length=1)
    grade: str | None = None  # None — без грейд-фильтра
    stack_must: list[str] = Field(default_factory=list)
    stack_nice: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)


class ExplanationFactorOut(BaseModel):
    factor: str
    weight: float
    value: float
    contribution: float
    human_text: str


class MatchItemOut(BaseModel):
    candidate_id: str
    score: float
    explanation: list[ExplanationFactorOut]
    in_category: bool  # False — блок «рядом с запросом» (PRD §7.5.2)
