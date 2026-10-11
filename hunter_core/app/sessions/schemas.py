"""Схемы сессий тестирования (контракт §8.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionCreateIn(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=64)
    spec: str = Field(min_length=1)
    grade_target: Literal["intern", "junior", "middle", "senior"]
    mode: Literal["full", "express"] = "full"


class InstanceOut(BaseModel):
    question_text: str
    payload: dict[str, Any]
    beta: float


class QuestionOut(BaseModel):
    template_id: str
    topic: str
    type: str
    time_limit: int
    instance: InstanceOut


class SessionCreatedOut(BaseModel):
    session_id: str
    question: QuestionOut


class AnswerIn(BaseModel):
    answer: str | int  # mcq: текст/индекс варианта; sql: текст запроса
    elapsed_ms: int | None = Field(default=None, ge=0)


class AskedItemOut(BaseModel):
    template_id: str
    seed: int
    topic: str
    kind: str
    beta: float
    correct: bool
    theta_after: float


class ResultOut(BaseModel):
    theta: float
    se: float
    outcome: str
    grade_verified: str | None
    grade_assigned: str
    grade_claimed: str
    spec: str
    mode: str
    p_upgrade: float
    p_downgrade: float
    asked: list[AskedItemOut]
    breakdown: dict[str, dict[str, int]]


class AnswerAcceptedOut(BaseModel):
    status: Literal["active"]
    correct: bool
    next_question: QuestionOut


class AnswerFinishedOut(BaseModel):
    status: Literal["finished"]
    correct: bool
    result: ResultOut
