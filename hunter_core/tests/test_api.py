"""API-тесты core-api: httpx AsyncClient + ASGITransport + asgi-lifespan.

Внешняя зависимость (PG) заменяется тестовой sqlite-файлом через env
CORE_DATABASE_URL — так проходит реальный lifespan (create_all + сборка
банка), без dependency_overrides. Выбор зафиксирован в отчёте: тестовая
sqlite через env, не overrides.
"""

import uuid

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.dependencies import verify_internal_token
from app.exceptions import UnauthorizedError
from app.main import create_app


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CORE_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/core.db")
    monkeypatch.setenv("CORE_ENV", "local")
    monkeypatch.setenv("CORE_BANK_SPECS", "backend")
    monkeypatch.setenv("CORE_BANK_MCQ_PER_SPEC", "6")
    monkeypatch.setenv("CORE_BANK_SQL_PER_SPEC", "4")
    monkeypatch.delenv("CORE_INTERNAL_TOKEN", raising=False)
    get_settings.cache_clear()
    app = create_app()
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    get_settings.cache_clear()


def _mcq_answer(question: dict) -> str:
    """Любой валидный ответ на вопрос (flow-тест, не проверка правильности)."""
    if question["type"] == "mcq":
        return question["instance"]["payload"]["options"][0]
    return "SELECT 1 WHERE 0"


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_catalog(client):
    resp = await client.get("/internal/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["specializations"]) == 7
    assert len(data["grades"]) == 4
    for g in data["grades"]:
        text = f"{g['title']} {g['description']}".lower()
        assert "опыт" not in text and "стаж" not in text and "лет" not in text


async def test_docs_visible_in_local_env(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"]


async def test_session_happy_path_express(client):
    resp = await client.post(
        "/internal/tests/sessions",
        json={"candidate_id": "cand-1", "spec": "backend", "grade_target": "middle",
              "mode": "express"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    session_id = data["session_id"]
    question = data["question"]
    assert question["type"] in ("mcq", "sql")
    assert question["time_limit"] > 0
    assert question["instance"]["question_text"]
    assert question["instance"]["payload"]

    asked_ids = set()
    for _step in range(3):  # express = 4 вопроса; первые 3 дают next_question
        resp = await client.post(
            f"/internal/tests/sessions/{session_id}/answers",
            json={"answer": _mcq_answer(question), "elapsed_ms": 12_000},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "active", data
        assert isinstance(data["correct"], bool)
        question = data["next_question"]
        assert question["template_id"] not in asked_ids
        asked_ids.add(question["template_id"])

    resp = await client.post(
        f"/internal/tests/sessions/{session_id}/answers",
        json={"answer": _mcq_answer(question), "elapsed_ms": 9_500},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "finished"
    result = data["result"]
    assert result["mode"] == "express"
    assert result["grade_claimed"] == "middle"
    assert result["outcome"] in ("confirmed", "upgrade_offer", "downgrade_offer")
    assert len(result["asked"]) == 4
    assert -4.0 <= result["theta"] <= 4.0
    assert result["se"] > 0
    assert result["breakdown"]

    # повторный ответ на завершённую сессию — 409
    resp = await client.post(
        f"/internal/tests/sessions/{session_id}/answers", json={"answer": "x"}
    )
    assert resp.status_code == 409


async def test_session_validation_errors(client):
    resp = await client.post(
        "/internal/tests/sessions",
        json={"candidate_id": "cand-1", "spec": "cooking", "grade_target": "middle"},
    )
    assert resp.status_code == 400
    resp = await client.post(
        f"/internal/tests/sessions/{uuid.uuid4().hex}/answers", json={"answer": "x"}
    )
    assert resp.status_code == 404


async def test_snapshots_match_and_category(client):
    strong = {
        "spec": "backend", "grade_verified": "middle", "theta": 1.4,
        "test_score": 0.8, "fsp_score": 0.7,
        "stack": ["python", "postgresql", "docker"],
    }
    weak_unverified = {
        "spec": "backend", "grade_verified": None, "theta": None,
        "test_score": 0.2, "fsp_score": 0.0, "stack": ["python"],
    }
    other_spec = {
        "spec": "frontend", "grade_verified": "senior", "theta": 2.5,
        "test_score": 0.9, "fsp_score": 0.5, "stack": ["javascript"],
    }
    for cid, snap in (("cand-strong", strong), ("cand-weak", weak_unverified),
                      ("cand-other", other_spec)):
        resp = await client.put(f"/internal/snapshots/{cid}", json=snap)
        assert resp.status_code == 200, resp.text
        assert resp.json()["candidate_id"] == cid
        assert resp.json()["updated_at"]

    resp = await client.post(
        "/internal/match",
        json={"spec": "backend", "grade": "middle", "stack_must": ["python"],
              "stack_nice": ["docker"]},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 2  # frontend-кандидат отфильтрован spec'ом
    by_id = {i["candidate_id"]: i for i in items}
    assert by_id["cand-strong"]["in_category"] is True
    assert by_id["cand-weak"]["in_category"] is False  # блок «рядом с запросом»
    assert items[0]["candidate_id"] == "cand-strong"  # категория идёт первой
    factors = {f["factor"] for f in by_id["cand-strong"]["explanation"]}
    assert factors == {"test", "stack", "fsp", "freshness"}

    resp = await client.get("/internal/category/backend/middle/ranking")
    assert resp.status_code == 200, resp.text
    ranking = resp.json()
    assert [i["candidate_id"] for i in ranking] == ["cand-strong"]
    stack_factor = next(f for f in ranking[0]["explanation"] if f["factor"] == "stack")
    assert stack_factor["value"] == 0.5  # нейтральная константа §7.5.4


async def test_match_validation_errors(client):
    resp = await client.post("/internal/match", json={"spec": "cooking"})
    assert resp.status_code == 400
    resp = await client.get("/internal/category/backend/architect/ranking")
    assert resp.status_code == 400


async def test_internal_token_dependency(monkeypatch):
    monkeypatch.setenv("CORE_INTERNAL_TOKEN", "secret")
    get_settings.cache_clear()
    with pytest.raises(UnauthorizedError):
        await verify_internal_token(x_internal_token="wrong")
    await verify_internal_token(x_internal_token="secret")
    get_settings.cache_clear()
