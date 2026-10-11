"""LLM-клиент: fallback без ключа, ретраи, страховка код-блоков (через MockTransport)."""

import httpx

from llm.client import LLMClient, reword_shell

ORIGINAL = "Что выведет этот фрагмент кода на Python?\n\n```python\nprint([1, 2])\n```"


def _client(handler, api_key="test-key"):
    return LLMClient(api_key=api_key, transport=httpx.MockTransport(handler), max_retries=3)


def _ok_handler(request):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": "Какой результат покажет этот код?\n\n"
                                              "```python\nprint([1, 2])\n```"}}]},
    )


def test_reword_fallback_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = LLMClient()
    assert not client.available
    assert reword_shell(ORIGINAL, "python", client) == ORIGINAL


def test_reword_success():
    client = _client(_ok_handler)
    out = reword_shell(ORIGINAL, "python", client)
    assert out != ORIGINAL
    assert "```python" in out  # код-блок сохранён


def test_reword_retries_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500, json={"error": "boom"})
        return _ok_handler(request)

    client = _client(handler)
    out = reword_shell(ORIGINAL, "python", client)
    assert calls["n"] == 3
    assert out != ORIGINAL


def test_reword_all_retries_fail_returns_original(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)

    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    client = _client(handler)
    assert reword_shell(ORIGINAL, "python", client) == ORIGINAL


def test_reword_network_error_returns_original(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)

    def handler(request):
        raise httpx.ConnectError("no route")

    client = _client(handler)
    assert reword_shell(ORIGINAL, "python", client) == ORIGINAL


def test_code_block_guard_falls_back():
    def handler(request):
        # модель «потеряла» код-блоки — ответ обязан быть отклонён
        return httpx.Response(200, json={"choices": [{"message": {"content": "просто текст"}}]})

    client = _client(handler)
    assert reword_shell(ORIGINAL, "python", client) == ORIGINAL


def test_cloudru_provider_config():
    """Провайдер cloudru: ДЦ РФ, ключ из CLOUDRU_API_KEY, модель Qwen3.6."""
    client = LLMClient(provider="cloudru", api_key="k")
    assert client.available
    assert client.base_url == "https://foundation-models.api.cloud.ru/v1"
    assert client.model == "Qwen/Qwen3.6-35B-A3B"


def test_provider_from_env(monkeypatch):
    monkeypatch.setenv("HUNTER_LLM_PROVIDER", "cloudru")
    monkeypatch.setenv("CLOUDRU_API_KEY", "env-key")
    monkeypatch.delenv("HUNTER_LLM_MODEL", raising=False)
    client = LLMClient()
    assert client.available
    assert "cloud.ru" in client.base_url


def test_unknown_provider_rejected():
    import pytest

    with pytest.raises(Exception, match="провайдер"):
        LLMClient(provider="nope", api_key="k")
