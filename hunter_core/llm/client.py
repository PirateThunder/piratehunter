"""LLM-клиент (OpenAI-совместимый) + перефразировка оболочек заданий (PRD §3.4).

Провайдер выбирается env HUNTER_LLM_PROVIDER:
- openrouter (дефолт): api.openrouter.ai, ключ OPENROUTER_API_KEY;
- cloudru: Cloud.ru Evolution Foundation Models (ДЦ в РФ — контур 152-ФЗ:
  персональные данные не покидают юрисдикцию), ключ CLOUDRU_API_KEY,
  модель по умолчанию Qwen/Qwen3.6-35B-A3B.

POST {base}/chat/completions, ретраи ×3 с экспоненциальной паузой, timeout.
reword_shell перефразирует легенду задания, НЕ меняя код/числа/варианты
(промпт это явно требует + проверка сохранности код-блоков); fallback: нет
ключа / ошибка / таймаут → исходный текст. Исключения наружу из reword_shell
не выбрасываются никогда — демо не зависит от сети и ключей.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

DEFAULT_TIMEOUT_S = 30.0
MAX_RETRIES = 3

PROVIDERS: dict[str, dict[str, str]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "model": "qwen/qwen-2.5-7b-instruct",
    },
    # Cloud.ru Evolution Foundation Models: serverless, ДЦ РФ, ₽/токен.
    # Qwen3.6 — reasoning-модель: без отключения thinking content приходит
    # пустым (паттерн из piratepitch: chat_template_kwargs.enable_thinking).
    "cloudru": {
        "base_url": "https://foundation-models.api.cloud.ru/v1",
        "key_env": "CLOUDRU_API_KEY",
        "model": "Qwen/Qwen3.6-35B-A3B",
        "no_thinking": "1",
    },
}

ENV_PROVIDER = "HUNTER_LLM_PROVIDER"
ENV_MODEL = "HUNTER_LLM_MODEL"


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        provider: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        max_retries: int = MAX_RETRIES,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        provider = provider or os.getenv(ENV_PROVIDER, "openrouter")
        if provider not in PROVIDERS:
            raise LLMError(
                f"неизвестный провайдер {provider!r}; доступны: {', '.join(PROVIDERS)}"
            )
        cfg = PROVIDERS[provider]
        key_env = cfg["key_env"]
        self._no_thinking = cfg.get("no_thinking") == "1"
        self.api_key = api_key if api_key is not None else os.getenv(key_env, "")
        self.model = model or os.getenv(ENV_MODEL) or cfg["model"]
        self.base_url = (base_url or cfg["base_url"]).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._http = httpx.Client(timeout=timeout, transport=transport)

    @classmethod
    def from_env(cls) -> LLMClient:
        return cls()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.4,
             max_tokens: int = 1200) -> str:
        """Один вызов chat/completions с ретраями; по исчерпании — LLMError."""
        if not self.available:
            raise LLMError("не задан API-ключ провайдера")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self._no_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self._http.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise LLMError(f"временная ошибка провайдера: HTTP {resp.status_code}")
                if resp.status_code >= 400:
                    raise LLMError(f"фатальная ошибка провайдера: HTTP {resp.status_code}")
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                if not isinstance(text, str) or not text.strip():
                    raise LLMError("пустой ответ модели")
                return text.strip()
            except (httpx.HTTPError, KeyError, ValueError, LLMError) as e:
                last_error = e
                fatal = isinstance(e, LLMError) and "фатальная" in str(e)
                if fatal or attempt == self.max_retries - 1:
                    break
                time.sleep(0.5 * (2**attempt))
        raise LLMError(f"LLM недоступна после {self.max_retries} попыток: {last_error}")


_REWORD_SYSTEM = (
    "Ты редактор тестовых заданий для ИТ-собеседований. Перефразируешь текст задания "
    "по-русски, сохраняя смысл и сложность. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО менять: блоки кода "
    "(```...```) и всё их содержимое, числа, имена переменных и функций, варианты "
    "ответов, значения и пороги. Меняется только легенда/формулировка вокруг кода. "
    "Ответ — только перефразированный текст задания, без комментариев."
)

_REWORD_USER = (
    "Тема задания: «{topic}». Перефразируй оболочку (легенду) этого задания, "
    "не трогая код, числа и варианты ответов:\n\n{text}"
)


def reword_shell(question_text: str, topic: str = "", client: LLMClient | None = None) -> str:
    """Перефразировка легенды задания; при любой проблеме — исходный текст.

    Дополнительная страховка: если в ответе модели изменилось число
    код-блоков (```), ответ отбрасывается — параметры задания и проверка
    не должны зависеть от LLM (PRD §7.4.1).
    """
    client = client or LLMClient.from_env()
    if not client.available:
        return question_text
    try:
        out = client.chat(
            [
                {"role": "system", "content": _REWORD_SYSTEM},
                {"role": "user", "content": _REWORD_USER.format(topic=topic or "программирование",
                                                               text=question_text)},
            ]
        )
    except Exception:
        return question_text
    if not out or out.count("```") != question_text.count("```"):
        return question_text
    return out
