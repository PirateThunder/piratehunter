"""Схемы прокси тест-сессий (ядро — core-api, §8.2)."""

from typing import Any, Literal

from pydantic import BaseModel

from ..constants import GRADES


class TestSessionStartIn(BaseModel):
    """POST /tests/sessions: заявляемый грейд, на который идёт тест.
    mode: full (10 вопросов) / express (4 вопроса, экспресс-режим для
    жюри §7.4.2); кулдауны §7.4.3 одинаковы для обоих режимов."""

    grade_target: Literal[*GRADES]
    mode: Literal["full", "express"] = "full"


class TestAnswerIn(BaseModel):
    """POST /tests/sessions/{id}/answers: ответ прозрачно проксируется
    в core. По контракту core-api answer — скаляр: mcq → int (индекс
    варианта), sql/code → str (текст решения)."""

    answer: str | int


class TestSessionOut(BaseModel):
    """Ответ core при старте: {session_id, question{...}} — проксируем
    как есть, оборачивая session_id для авторизации владельца."""

    session_id: str
    question: dict[str, Any] | None = None


class TestAnswerOut(BaseModel):
    """Ответ core на ответ: ровно одно из next_question / result."""

    next_question: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
