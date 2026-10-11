"""OpenRouter LLM-клиент + перефразировка оболочек заданий (PRD §3.4).

Минимальный AIClient: POST https://openrouter.ai/api/v1/chat/completions,
ключ из env OPENROUTER_API_KEY, модель из env HUNTER_LLM_MODEL (дефолт —
недорогая qwen-2.5-7b-instruct), ретраи ×3 с экспоненциальной паузой,
timeout. reword_shell перефразирует легенду задания, НЕ меняя код/числа/
варианты (промпт это явно требует + проверка сохранности код-блоков);
fallback: нет ключа / ошибка / таймаут → исходный текст. Исключения наружу
из reword_shell не выбрасываются никогда — демо не зависит от сети и ключей.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "qwen/qwen-2.5-7b-instruct"
DEFAULT_TIMEOUT_S = 30.0
MAX_RETRIES = 3

ENV_API_KEY = "OPENROUTER_API_KEY"
ENV_MODEL = "HUNTER_LLM_MODEL"


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_S,
        max_retries: int = MAX_RETRIES,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv(ENV_API_KEY, "")
        self.model = model or os.getenv(ENV_MODEL) or DEFAULT_MODEL
        self.base_url = base_url.rstrip("/")
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
            raise LLMError(f"не задан {ENV_API_KEY}")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
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
