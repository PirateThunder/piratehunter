"""Тесты POST /internal/llm/parse-need: fallback без ключа, устойчивость к
невалидному/падающему LLM (моки, сеть не дёргается), валидация запроса."""

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.llm_parse import service
from app.main import create_app
from llm.client import LLMClient, LLMError

FRONTEND_TEXT = (
    "Нужен senior frontend-разработчик, обязательно React и TypeScript, "
    "желательно Next.js"
)
BACKEND_TEXT = "Ищем мидла на FastAPI, PostgreSQL и Redis, 250–350к"


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


async def test_fallback_without_key_frontend(client):
    resp = await client.post("/internal/llm/parse-need", json={"raw_text": FRONTEND_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] == "frontend"
    assert data["grade"] == "senior"
    assert "react" in data["stack_must"] and "typescript" in data["stack_must"]
    assert "nextjs" in data["stack_nice"]
    assert data["confidence"] <= 0.4
    assert "без LLM" in data["notes"]


async def test_fallback_backend_ru(client):
    resp = await client.post("/internal/llm/parse-need", json={"raw_text": BACKEND_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] == "backend"
    assert data["grade"] == "middle"
    assert {"fastapi", "postgresql", "redis"} <= set(data["stack_must"])


async def test_empty_raw_text_422(client):
    assert (await client.post("/internal/llm/parse-need",
                              json={"raw_text": ""})).status_code == 422
    assert (await client.post("/internal/llm/parse-need",
                              json={"raw_text": "   "})).status_code == 422
    assert (await client.post("/internal/llm/parse-need",
                              json={})).status_code == 422


def _fake_chat(payload: str | Exception):
    def fake(self, messages, temperature=0.4, max_tokens=1200):
        if isinstance(payload, Exception):
            raise payload
        return payload

    return fake


async def test_llm_invalid_spec_dropped_to_null(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        LLMClient, "chat",
        _fake_chat('{"spec": "cooking", "grade": "senior", "stack_must": ["React"], '
                   '"stack_nice": [], "notes": "понял так"}'),
    )
    resp = await client.post("/internal/llm/parse-need", json={"raw_text": FRONTEND_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] is None  # невалидный slug отброшен
    assert data["grade"] == "senior"
    assert data["stack_must"] == ["react"]  # нормализация регистра
    assert data["confidence"] >= 0.8
    assert data["notes"] == "понял так"


async def test_llm_fenced_json_and_noise(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        LLMClient, "chat",
        _fake_chat('Вот ответ:\n```json\n{"spec": "qa", "grade": "junior", '
                   '"stack_must": ["pytest", "selenium"], "stack_nice": [], '
                   '"notes": "qa-джун"}\n```\nНадеюсь, помогло'),
    )
    resp = await client.post("/internal/llm/parse-need",
                             json={"raw_text": "ищем джуниор-тестировщика"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] == "qa" and data["grade"] == "junior"
    assert data["stack_must"] == ["pytest", "selenium"]
    assert data["confidence"] >= 0.8


async def test_llm_exception_falls_back_200(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(LLMClient, "chat", _fake_chat(LLMError("сеть недоступна")))
    resp = await client.post("/internal/llm/parse-need", json={"raw_text": FRONTEND_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] == "frontend"  # fallback по keyword-правилам
    assert data["grade"] == "senior"
    assert data["confidence"] <= 0.4
    assert "LLM недоступна" in data["notes"]


async def test_llm_garbage_answer_falls_back(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(LLMClient, "chat", _fake_chat("совсем не JSON"))
    resp = await client.post("/internal/llm/parse-need", json={"raw_text": BACKEND_TEXT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] == "backend"  # fallback
    assert data["confidence"] <= 0.4


# ---------------------------------------------------------- сервисный уровень


def test_fallback_service_sync_no_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    out = service.parse_need("Нужен devops-инженер: kubernetes, terraform, linux")
    assert out.spec == "devops"
    assert {"kubernetes", "terraform", "linux"} <= set(out.stack_must)
    out = service.parse_need("Ищем стажёра-тестировщика, pytest будет плюсом")
    assert out.spec == "qa"
    assert out.grade == "intern"
    assert out.stack_must == [] and "pytest" in out.stack_nice
    out = service.parse_need("Просто хорошего человека в команду")
    assert out.spec is None and out.grade is None
    assert out.confidence <= 0.2
