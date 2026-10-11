"""Сервис сессий тестирования: движок ↔ строки БД (state в PG, PRD §4.4).

Тяжёлая sync-работа движка (генерация экземпляров — exec/sqlite) вынесена в
run_in_threadpool на уровне роутера. Состояние сессии не кешируется в
памяти: каждый запрос восстанавливает TestEngine из строк БД
(TestEngine.restore), экземпляр открытого вопроса переинстанцируется по
(template_id, seed) — генерация детерминирована.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models import AnswerModel, BetaStatModel, TestSessionModel, utcnow
from engine import irt
from engine.cat import AskedItem, CatConfig, TestEngine
from engine.catalog import get_grade, get_specialization
from itembank.model import Instance
from itembank.registry import BankRegistry

CALIB_WINDOW = irt.CALIB_MIN_N


def question_dict(inst: Instance) -> dict[str, Any]:
    return {
        "template_id": inst.template_id,
        "topic": inst.topic,
        "type": inst.kind,
        "time_limit": inst.time_limit_s,
        "instance": {
            "question_text": inst.question_text,
            "payload": inst.payload,
            "beta": inst.beta,
        },
    }


def create_session_sync(
    bank: BankRegistry, session_id: str, spec: str, grade_target: str, mode: str
) -> tuple[Instance, float]:
    """Старт сессии в движке (sync; вызывать через run_in_threadpool)."""
    try:
        get_specialization(spec)
        get_grade(grade_target)
    except ValueError as e:
        raise BadRequestError(str(e)) from e
    if not bank.filter(spec=spec):
        raise BadRequestError(f"в банке нет активных шаблонов специализации {spec!r}")
    engine = TestEngine(bank, seed=f"session:{session_id}")
    inst = engine.start(spec, grade_target, mode)
    return inst, engine.theta


async def create_session(
    db: AsyncSession, *, session_id: str, candidate_id: str, spec: str,
    grade_target: str, mode: str, inst: Instance, theta: float,
) -> None:
    row = TestSessionModel(
        id=session_id,
        candidate_id=candidate_id,
        spec_slug=spec,
        grade_target=grade_target,
        mode=mode,
        theta=theta,
        se=None,  # до первого ответа SE = inf
        asked_template_ids=[],
        seeds=[],
        pending_template_id=inst.template_id,
        pending_seed=inst.seed,
        status="active",
    )
    db.add(row)
    await db.commit()


def submit_answer_sync(
    bank: BankRegistry,
    row: TestSessionModel,
    answer_rows: list[AnswerModel],
    answer: str | int,
) -> dict[str, Any]:
    """Ответ движку на восстановленном состоянии (sync; через run_in_threadpool)."""
    asked = [
        AskedItem(
            template_id=a.template_id,
            seed=a.seed,
            topic=bank.get(a.template_id).topic,
            kind=bank.get(a.template_id).kind,
            beta=bank.get(a.template_id).beta,
            correct=a.correct,
            theta_after=a.theta_after,
        )
        for a in answer_rows
    ]
    template = bank.get(row.pending_template_id or "")
    inst = template.make(row.pending_seed or 0)
    engine = TestEngine.restore(
        bank,
        spec=row.spec_slug,
        grade_claimed=row.grade_target,
        mode=row.mode,
        theta=row.theta,
        asked=asked,
        pending=(template, inst),
        config=CatConfig(),
        seed=f"session:{row.id}:{len(asked)}",
    )
    out = engine.submit(answer)
    response: dict[str, Any] = {
        "correct": out["correct"],
        "answered": asdict(engine.asked[-1]),
        "theta": engine.theta,
        "se": None if math.isinf(engine.se) else engine.se,
    }
    if out["finished"]:
        response["result"] = out["result"]
    else:
        response["next_instance"] = out["next"]
    return response


async def submit_session(
    db: AsyncSession, bank: BankRegistry, session_id: str, outcome: dict[str, Any],
    elapsed_ms: int | None = None,
) -> None:
    """Персистит ответ и новое состояние; калибрует BetaStat шаблона (§7.4.5)."""
    row = await db.get(TestSessionModel, session_id)
    assert row is not None  # проверено в роутере до sync-части
    answered = outcome["answered"]
    db.add(
        AnswerModel(
            session_id=session_id,
            template_id=answered["template_id"],
            seed=answered["seed"],
            correct=outcome["correct"],
            elapsed_ms=elapsed_ms,
            theta_after=answered["theta_after"],
        )
    )
    row.theta = outcome["theta"]
    row.se = outcome["se"]
    row.asked_template_ids = [*row.asked_template_ids, answered["template_id"]]
    row.seeds = [*row.seeds, answered["seed"]]
    if "result" in outcome:
        row.status = "finished"
        row.finished_at = utcnow()
        row.result = outcome["result"]
        row.pending_template_id = None
        row.pending_seed = None
    else:
        nxt: Instance = outcome["next_instance"]
        row.pending_template_id = nxt.template_id
        row.pending_seed = nxt.seed

    stat = await db.get(BetaStatModel, answered["template_id"])
    if stat is None:
        stat = BetaStatModel(
            template_id=answered["template_id"],
            beta=bank.get(answered["template_id"]).beta,
            n_answers=0,
            window=[],
        )
    window = [*stat.window, [answered["theta_after"], 1 if outcome["correct"] else 0]]
    stat.n_answers += 1
    if len(window) >= CALIB_WINDOW:
        beta_stat = irt.BetaStat(template_id=stat.template_id, beta=stat.beta)
        for th, corr in window:
            beta_stat.record(th, bool(corr))
        stat.beta = beta_stat.calibrate(min_n=CALIB_WINDOW) or stat.beta
        bank.get(stat.template_id).beta = stat.beta  # in-memory банк следом за БД
        window = []
    stat.window = window
    db.add(stat)
    await db.commit()


async def get_session_row(db: AsyncSession, session_id: str) -> TestSessionModel:
    row = await db.get(TestSessionModel, session_id)
    if row is None:
        raise NotFoundError(f"сессия {session_id!r} не найдена")
    return row


async def get_active_session_row(db: AsyncSession, session_id: str) -> TestSessionModel:
    row = await get_session_row(db, session_id)
    if row.status != "active":
        raise ConflictError(f"сессия {session_id!r} уже завершена")
    return row


async def list_answers(db: AsyncSession, session_id: str) -> list[AnswerModel]:
    q = select(AnswerModel).where(AnswerModel.session_id == session_id).order_by(AnswerModel.id)
    return list((await db.execute(q)).scalars())
