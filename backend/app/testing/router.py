"""Прокси тест-движка core-api (PRD §8.1 → §8.2): старт сессии и
ответы. Backend владеет авторизацией владельца сессии (Redis-маппинг
session→candidate), кулдаунами §7.4.3 и применением результата к
GradeState + пушем снапшота. Сама CAT-логика — в core."""

import logging

from fastapi import APIRouter, HTTPException

from ..auth.dependencies import CandidateUser
from ..candidates import service as candidates_service
from ..core_client.client import CoreDep, CoreError
from ..database import DbDep
from ..redis import RedisDep
from .schemas import (
    TestAnswerIn,
    TestAnswerOut,
    TestSessionOut,
    TestSessionStartIn,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tests"])

_OWNER_KEY = "tses:{session_id}"
_OWNER_TTL = 2 * 3600  # сек; сессия экспресса — минуты, запас на полный


def _raise_core(e: CoreError) -> None:
    """Ошибки core: 4xx пробрасываем как есть (валидация ответа,
    состояние сессии — ответственность ядра), остальное → 502."""
    if e.status_code is not None and 400 <= e.status_code < 500:
        raise HTTPException(e.status_code, f"core-api: {e}") from e
    raise HTTPException(502, f"core-api: {e}") from e


@router.post(
    "/tests/sessions",
    response_model=TestSessionOut,
    status_code=201,
    summary="Начать тест на грейд (первая задача)",
    description="mode=express — экспресс-тест на 3–5 минут для жюри "
    "(§7.4.2), та же шкала θ и те же кулдауны §7.4.3.",
)
async def start_session(
    body: TestSessionStartIn,
    user: CandidateUser,
    session: DbDep,
    redis: RedisDep,
    core: CoreDep,
) -> TestSessionOut:
    """Старт CAT-сессии: кулдауны §7.4.3 (409 при ранней смене грейда),
    затем core выдаёт первую задачу. ПДн в core не уходят — только
    candidate_id, специализация, целевой грейд и режим."""
    profile = await candidates_service.get_profile_or_404(session, user.id)
    if profile.spec_slug is None:
        raise HTTPException(
            422, "сначала выберите специализацию в профиле"
        )
    grade_state = await candidates_service.get_grade_state(session, user.id)
    candidates_service.check_test_cooldown(grade_state, body.grade_target)
    try:
        data = await core.start_session(
            user.id, profile.spec_slug, body.grade_target, body.mode
        )
    except CoreError as e:
        _raise_core(e)
    session_id = data.get("session_id")
    if not session_id:
        raise HTTPException(502, "core-api: ответ без session_id")
    await redis.setex(_OWNER_KEY.format(session_id=session_id),
                      _OWNER_TTL, user.id)
    return TestSessionOut(session_id=session_id, question=data.get("question"))


@router.post(
    "/tests/sessions/{session_id}/answers",
    response_model=TestAnswerOut,
    summary="Ответить на задачу (следующая задача или результат)",
)
async def answer(
    session_id: str,
    body: TestAnswerIn,
    user: CandidateUser,
    session: DbDep,
    redis: RedisDep,
    core: CoreDep,
) -> TestAnswerOut:
    """Ответ → core: {next_question} | {result}. На result обновляем
    GradeState (грейд — только по тесту, §6) и пушим снапшот в core."""
    owner = await redis.get(_OWNER_KEY.format(session_id=session_id))
    if isinstance(owner, bytes):
        owner = owner.decode()
    if owner is None or owner != user.id:
        raise HTTPException(404, "тест-сессия не найдена")
    try:
        data = await core.answer(session_id, body.answer)
    except CoreError as e:
        _raise_core(e)
    result = data.get("result")
    if result is not None:
        profile = await candidates_service.get_profile_or_404(
            session, user.id
        )
        await candidates_service.apply_test_result(
            session, core, profile, result
        )
        await redis.delete(_OWNER_KEY.format(session_id=session_id))
    return TestAnswerOut(
        next_question=data.get("next_question"), result=result
    )
