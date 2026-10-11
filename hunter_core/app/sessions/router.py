"""Роутер сессий тестирования (контракт §8.2)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_bank, get_db
from app.sessions import service
from app.sessions.schemas import (
    AnswerAcceptedOut,
    AnswerFinishedOut,
    AnswerIn,
    SessionCreatedOut,
    SessionCreateIn,
)
from itembank.registry import BankRegistry

router = APIRouter(prefix="/tests", tags=["tests"])

BankDep = Annotated[BankRegistry, Depends(get_bank)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/sessions",
    response_model=SessionCreatedOut,
    status_code=status.HTTP_201_CREATED,
    summary="Старт тест-сессии → первый вопрос",
)
async def create_session(
    payload: SessionCreateIn,
    bank: BankDep,
    db: DbDep,
) -> SessionCreatedOut:
    session_id = uuid.uuid4().hex
    inst, theta = await run_in_threadpool(
        service.create_session_sync,
        bank,
        session_id,
        payload.spec,
        payload.grade_target,
        payload.mode,
    )
    await service.create_session(
        db,
        session_id=session_id,
        candidate_id=payload.candidate_id,
        spec=payload.spec,
        grade_target=payload.grade_target,
        mode=payload.mode,
        inst=inst,
        theta=theta,
    )
    return SessionCreatedOut(session_id=session_id, question=service.question_dict(inst))


@router.post(
    "/sessions/{session_id}/answers",
    response_model=AnswerAcceptedOut | AnswerFinishedOut,
    summary="Ответ на текущий вопрос → следующий вопрос | результат",
)
async def submit_answer(
    session_id: str,
    payload: AnswerIn,
    bank: BankDep,
    db: DbDep,
) -> AnswerAcceptedOut | AnswerFinishedOut:
    row = await service.get_active_session_row(db, session_id)
    answers = await service.list_answers(db, session_id)
    outcome = await run_in_threadpool(
        service.submit_answer_sync, bank, row, answers, payload.answer
    )
    await service.submit_session(db, bank, session_id, outcome, elapsed_ms=payload.elapsed_ms)
    if "result" in outcome:
        return AnswerFinishedOut(
            status="finished", correct=outcome["correct"], result=outcome["result"]
        )
    return AnswerAcceptedOut(
        status="active",
        correct=outcome["correct"],
        next_question=service.question_dict(outcome["next_instance"]),
    )
