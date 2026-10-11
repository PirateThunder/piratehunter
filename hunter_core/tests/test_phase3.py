"""Тесты фазы 3: DELETE /internal/snapshots (идемпотентная очистка) и
POST /internal/llm/parse-resume (fallback без ключа, мокнутый LLM, 422).
Сеть нигде не дёргается."""

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app
from app.resume_parse import service
from llm.client import LLMClient, LLMError

RESUME_TEXT = """Иванов Иван, backend-разработчик.

Опыт: 3 года коммерческой разработки на Python. Проектировал REST API
на FastAPI, работал с PG (PostgreSQL) и Redis, деплой в Docker и k8s.
Писал тесты на pytest, настраивал CI в GitLab.

О себе: люблю чистый код и понятные архитектуры, читаю книги по системному
дизайну, выступаю на внутренних митапах компании.
"""


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CORE_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/core.db")
    monkeypatch.setenv("CORE_ENV", "local")
    monkeypatch.setenv("CORE_BANK_SPECS", "backend")
    monkeypatch.setenv("CORE_BANK_MCQ_PER_SPEC", "3")
    monkeypatch.setenv("CORE_BANK_SQL_PER_SPEC", "2")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    get_settings.cache_clear()
    app = create_app()
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    get_settings.cache_clear()


# ------------------------------------------------------- DELETE /snapshots


async def test_delete_snapshots_clears_only_snapshots(client):
    for cid in ("cand-1", "cand-2"):
        resp = await client.put(
            f"/internal/snapshots/{cid}",
            json={"spec": "backend", "grade_verified": "middle", "test_score": 0.7},
        )
        assert resp.status_code == 200
    resp = await client.post("/internal/match", json={"spec": "backend"})
    assert len(resp.json()) == 2

    resp = await client.delete("/internal/snapshots")
    assert resp.status_code == 204
    assert resp.content == b""
    resp = await client.post("/internal/match", json={"spec": "backend"})
    assert resp.json() == []

    # каталог и банк не тронуты: сессия теста создаётся
    resp = await client.post(
        "/internal/tests/sessions",
        json={"candidate_id": "cand-1", "spec": "backend", "grade_target": "middle"},
    )
    assert resp.status_code == 201


async def test_delete_snapshots_idempotent(client):
    assert (await client.delete("/internal/snapshots")).status_code == 204
    assert (await client.delete("/internal/snapshots")).status_code == 204


# ------------------------------------------------------- parse-resume


async def test_resume_fallback_without_key(client):
    resp = await client.post("/internal/llm/parse-resume", json={"text": RESUME_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] == "backend"
    assert "fastapi" in data["stack"]
    assert "postgresql" in data["stack"]  # PG нормализован
    assert "kubernetes" in data["stack"]  # k8s нормализован
    assert "backend-разработчик" in data["roles"]
    assert data["experience_years"] == 3
    assert data["grade_claimed"] == "middle"  # маркеров нет → подсказка по стажу
    assert data["about"] and len(data["about"]) <= 500
    assert data["confidence"] <= 0.35
    assert "без LLM" in data["notes"]


async def test_resume_email_pattern_does_not_reject(client, caplog):
    text = RESUME_TEXT + "\nКонтакты: ivanov@example.com"
    with caplog.at_level("WARNING", logger="app.resume_parse"):
        resp = await client.post("/internal/llm/parse-resume", json={"text": text})
    assert resp.status_code == 200
    assert any("email" in rec.message for rec in caplog.records)


async def test_resume_empty_text_422(client):
    assert (await client.post("/internal/llm/parse-resume",
                              json={"text": ""})).status_code == 422
    assert (await client.post("/internal/llm/parse-resume",
                              json={"text": "  \n "})).status_code == 422
    assert (await client.post("/internal/llm/parse-resume",
                              json={})).status_code == 422


def _fake_chat(payload: str | Exception):
    def fake(self, messages, temperature=0.4, max_tokens=1200):
        if isinstance(payload, Exception):
            raise payload
        return payload

    return fake


async def test_resume_llm_valid(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        LLMClient, "chat",
        _fake_chat('{"spec": "backend", "grade_claimed": "middle", '
                   '"stack": ["FastAPI", "PG", "Redis"], '
                   '"roles": ["Backend-разработчик"], "experience_years": 3, '
                   '"about": "Python-разработчик, 3 года."}'),
    )
    resp = await client.post("/internal/llm/parse-resume", json={"text": RESUME_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] == "backend" and data["grade_claimed"] == "middle"
    assert data["stack"] == ["fastapi", "postgresql", "redis"]
    assert data["roles"] == ["backend-разработчик"]
    assert data["experience_years"] == 3
    assert data["about"] == "Python-разработчик, 3 года."
    assert data["confidence"] >= 0.8


async def test_resume_llm_invalid_spec_dropped(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        LLMClient, "chat",
        _fake_chat('{"spec": "cooking", "grade_claimed": "architect", "stack": [], '
                   '"roles": [], "experience_years": "5 лет", "about": null}'),
    )
    resp = await client.post("/internal/llm/parse-resume", json={"text": RESUME_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] is None and data["grade_claimed"] is None
    assert data["experience_years"] == 5  # строка приведена к int
    assert data["confidence"] == pytest.approx(0.8)


async def test_resume_llm_exception_falls_back(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(LLMClient, "chat", _fake_chat(LLMError("сеть недоступна")))
    resp = await client.post("/internal/llm/parse-resume", json={"text": RESUME_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] == "backend"
    assert data["confidence"] <= 0.35
    assert "LLM недоступна" in data["notes"]


def test_resume_fallback_service_sync(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    out = service.parse_resume("Frontend-разработчик, 6 лет опыта. React, TypeScript, "
                               "Next.js. Веду команду как тимлид.")
    assert out.spec == "frontend"
    assert out.grade_claimed == "senior"
    assert "тимлид" in out.roles
    assert out.experience_years == 6
    out = service.parse_resume("Хочу в IT, пока без опыта.")
    assert out.spec is None and out.stack == []
    assert out.confidence <= 0.2
