"""Прокси тест-движка: старт/ответы, владелец сессии, результат →
GradeState + снапшот, кулдауны §7.4.3 (§16.3 приёмки)."""

from datetime import UTC, datetime, timedelta

from app.candidates.models import GradeState
from app.config import get_settings
from tests.conftest import make_candidate


async def _start(client, headers, grade="middle"):
    return await client.post(
        "/api/v1/tests/sessions",
        json={"grade_target": grade},
        headers=headers,
    )


async def test_start_calls_core_and_returns_question(client, fake_core):
    headers, user = await make_candidate(client)
    resp = await _start(client, headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["session_id"]
    assert data["question"]["type"] == "mcq"
    assert fake_core.started == [
        {"candidate_id": user["id"], "spec": "backend",
         "grade_target": "middle", "mode": "full"}
    ]


async def test_express_mode_forwarded(client, fake_core):
    """Экспресс-режим §7.4.2: mode прокидывается в core как есть."""
    headers, user = await make_candidate(client)
    resp = await client.post(
        "/api/v1/tests/sessions",
        json={"grade_target": "middle", "mode": "express"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert fake_core.started[-1] == {
        "candidate_id": user["id"], "spec": "backend",
        "grade_target": "middle", "mode": "express",
    }
    # кулдауны те же: повторный express на тот же грейд после подтверждения
    # — 409 (см. test_retest_cooldown_409, логика общая)


async def test_start_bad_mode_422(client):
    headers, _ = await make_candidate(client)
    resp = await client.post(
        "/api/v1/tests/sessions",
        json={"grade_target": "middle", "mode": "lightning"},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_start_requires_profile_and_spec(client):
    from tests.conftest import register_via_email, select_role

    headers, _ = await register_via_email(client)
    await select_role(client, headers, "candidate")
    assert (await _start(client, headers)).status_code == 404


async def test_answer_result_updates_grade_state_and_snapshot(
    client, fake_core, session_factory
):
    headers, user = await make_candidate(client)
    session_id = (await _start(client, headers)).json()["session_id"]
    resp = await client.post(
        f"/api/v1/tests/sessions/{session_id}/answers",
        json={"answer": 1},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["outcome"] == "confirmed"
    async with session_factory() as session:
        state = await session.get(GradeState, user["id"])
        assert state.grade_verified == "middle"
        assert state.status == "confirmed"
        assert state.theta == 1.2
        assert state.last_test_at is not None
        assert state.grade_changed_at is not None
    # снапшот с подтверждённым грейдом ушёл в core (§4.3)
    pushes = [s for cid, s in fake_core.snapshots if cid == user["id"]]
    assert pushes[-1]["grade_verified"] == "middle"
    assert pushes[-1]["theta"] == 1.2


async def test_answer_next_question_passthrough(client, fake_core):
    headers, _ = await make_candidate(client)
    session_id = (await _start(client, headers)).json()["session_id"]
    fake_core.answer_script = [
        {"next_question": {"type": "sql", "instance": {"text": "select"}}},
    ]
    resp = await client.post(
        f"/api/v1/tests/sessions/{session_id}/answers",
        json={"answer": 0},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["next_question"]["type"] == "sql"
    assert resp.json()["result"] is None


async def test_answer_foreign_session_404(client, fake_core):
    headers, _ = await make_candidate(client)
    other_headers, _ = await make_candidate(client)
    session_id = (await _start(client, headers)).json()["session_id"]
    resp = await client.post(
        f"/api/v1/tests/sessions/{session_id}/answers",
        json={"answer": 0},
        headers=other_headers,
    )
    assert resp.status_code == 404


async def test_retest_cooldown_409(client, fake_core, session_factory,
                                   monkeypatch):
    """Повтор теста на текущий грейд раньше 30 дней — 409 (§7.4.3)."""
    headers, user = await make_candidate(client)
    session_id = (await _start(client, headers)).json()["session_id"]
    await client.post(
        f"/api/v1/tests/sessions/{session_id}/answers",
        json={"answer": 0},
        headers=headers,
    )
    resp = await _start(client, headers)  # тот же грейд — 409
    assert resp.status_code == 409
    assert "повторный тест" in resp.json()["detail"]
    # кулдаун истёк — можно
    async with session_factory() as session:
        state = await session.get(GradeState, user["id"])
        state.last_test_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            days=31
        )
        await session.commit()
    assert (await _start(client, headers)).status_code == 201


async def test_grade_change_cooldown_409(client, fake_core, session_factory):
    """Смена подтверждённого грейда раньше 90 дней — 409 (§16.3)."""
    headers, user = await make_candidate(client)
    session_id = (await _start(client, headers)).json()["session_id"]
    await client.post(
        f"/api/v1/tests/sessions/{session_id}/answers",
        json={"answer": 0},
        headers=headers,
    )
    resp = await _start(client, headers, grade="senior")
    assert resp.status_code == 409
    assert "смена грейда" in resp.json()["detail"]
    # 91 день — можно
    async with session_factory() as session:
        state = await session.get(GradeState, user["id"])
        state.grade_changed_at = datetime.now(UTC).replace(
            tzinfo=None
        ) - timedelta(days=91)
        await session.commit()
    assert (await _start(client, headers, grade="senior")).status_code == 201


async def test_downgrade_after_offer_no_cooldown(client, fake_core,
                                                 session_factory):
    """Провал и уход на грейд ниже — без сжигания попытки (Q&A):
    при downgrade_offer тест ниже не проверяет 90-дневный кулдаун."""
    headers, user = await make_candidate(client)
    fake_core.answer_script = [
        {"result": {"theta": -0.5, "se": 0.4, "outcome": "downgrade_offer",
                    "grade_verified": None, "breakdown": {}}},
    ]
    session_id = (await _start(client, headers, grade="senior")).json()[
        "session_id"
    ]
    # фиксируем, что был подтверждённый middle (менее 90 дней назад)
    async with session_factory() as session:
        session.add(
            GradeState(
                candidate_id=user["id"],
                grade_verified="middle",
                theta=1.0,
                grade_changed_at=datetime.now(UTC).replace(tzinfo=None),
                status="confirmed",
            )
        )
        await session.commit()
    await client.post(
        f"/api/v1/tests/sessions/{session_id}/answers",
        json={"answer": 0},
        headers=headers,
    )
    async with session_factory() as session:
        state = await session.get(GradeState, user["id"])
        assert state.status == "downgrade_offer"
        assert state.grade_verified == "middle"  # принудительно не понижаем
    # тест на junior (ниже) — сразу, без 90-дневного кулдауна
    resp = await _start(client, headers, grade="junior")
    assert resp.status_code == 201, resp.text


async def test_get_grade_returns_state_and_cooldowns(client, fake_core):
    headers, user = await make_candidate(client)
    session_id = (await _start(client, headers)).json()["session_id"]
    await client.post(
        f"/api/v1/tests/sessions/{session_id}/answers",
        json={"answer": 0},
        headers=headers,
    )
    fake_core.ranking = [
        {"candidate_id": "someone-else", "score": 0.9},
        {"candidate_id": user["id"], "score": 0.8},
    ]
    resp = await client.get("/api/v1/candidate/grade", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["grade_verified"] == "middle"
    assert data["status"] == "confirmed"
    assert data["theta"] == 1.2
    assert data["retest_available_at"] is not None
    assert data["change_available_at"] is not None
    assert data["category_rank"] == 2
    assert data["category_size"] == 2


async def test_cooldown_days_from_config(client, fake_core, session_factory,
                                         monkeypatch):
    """Сроки кулдаунов — конфиг (§7.4.3), а не константы в коде."""
    monkeypatch.setattr(get_settings(), "grade_change_cooldown_days", 0)
    monkeypatch.setattr(get_settings(), "retest_cooldown_days", 0)
    headers, _ = await make_candidate(client)
    session_id = (await _start(client, headers)).json()["session_id"]
    await client.post(
        f"/api/v1/tests/sessions/{session_id}/answers",
        json={"answer": 0},
        headers=headers,
    )
    assert (await _start(client, headers)).status_code == 201
    assert (await _start(client, headers, grade="senior")).status_code == 201
