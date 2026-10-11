"""HTTP-клиент core-api (hunter_core) — единственная точка связи с
тест-движком и матчингом, контракт PRD §8.2.

Бизнес-логика (CAT, скоринг, объяснения) живёт в core; backend только
оркестрирует и владеет ПДн: в core уходят лишь candidate_id и структура
потребности — никаких ФИО/контактов (privacy by design, §4.2).
"""

import logging
from typing import Annotated, Any

import httpx
from fastapi import Depends

from ..config import get_settings

logger = logging.getLogger(__name__)


class CoreError(Exception):
    """Ошибка вызова core-api (→ 502 наружу, если не обработана)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CoreClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=(base_url or get_settings().core_api_url).rstrip("/"),
            timeout=httpx.Timeout(30.0),
            transport=transport,
            # внутренний трафик не уходит в прокси из окружения
            trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        try:
            resp = await self._client.request(method, url, **kwargs)
        except httpx.TransportError as e:
            raise CoreError(f"core-api недоступен: {e}") from e
        if resp.status_code >= 400:
            raise CoreError(
                f"core-api ответил {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )
        return resp

    # --- справочник (§6): специализации/грейды/темы ---

    async def get_catalog(self) -> dict:
        resp = await self._request("GET", "/internal/catalog")
        return resp.json()

    # --- тест-сессии (CAT-lite, §7.4) ---

    async def start_session(
        self,
        candidate_id: str,
        spec: str,
        grade_target: str,
        mode: str = "full",
    ) -> dict:
        """POST /internal/tests/sessions → {session_id, question}.
        mode: full (10 вопросов) | express (4 вопроса, §7.4.2)."""
        resp = await self._request(
            "POST",
            "/internal/tests/sessions",
            json={
                "candidate_id": candidate_id,
                "spec": spec,
                "grade_target": grade_target,
                "mode": mode,
            },
        )
        return resp.json()

    async def answer(self, session_id: str, answer: Any) -> dict:
        """POST …/answers → {next_question} | {result{theta, se, outcome,
        grade_verified, breakdown}}. Тело core — объект {answer, ...}."""
        resp = await self._request(
            "POST",
            f"/internal/tests/sessions/{session_id}/answers",
            json={"answer": answer},
        )
        return resp.json()

    # --- оценочные снапшоты (§4.3) ---

    async def push_snapshot(self, candidate_id: str, snapshot: dict) -> None:
        """PUT /internal/snapshots/{candidate_id} — пуш после изменений
        (тест пройден, ФСП привязан, профиль обновлён)."""
        await self._request(
            "PUT", f"/internal/snapshots/{candidate_id}", json=snapshot
        )

    async def delete_snapshots(self) -> None:
        """DELETE /internal/snapshots → 204: полная очистка снапшотов
        перед реседом (контракт фазы 3)."""
        await self._request("DELETE", "/internal/snapshots")

    # --- матчинг (§7.5) ---

    async def match(self, need: dict) -> list[dict]:
        """POST /internal/match → [{candidate_id, score, explanation}]."""
        resp = await self._request("POST", "/internal/match", json=need)
        return resp.json()

    # --- LLM-разбор потребности (§7.5.1, экран «мы поняли так» §7.3) ---

    async def llm_parse_need(self, raw_text: str) -> dict:
        """POST /internal/llm/parse-need {raw_text} → {spec, grade,
        stack_must, stack_nice, confidence, notes}. Внутри core — LLM с
        keyword-fallback; ПДн в raw_text нет (§3.4)."""
        resp = await self._request(
            "POST", "/internal/llm/parse-need", json={"raw_text": raw_text}
        )
        return resp.json()

    async def parse_resume(self, text: str) -> dict:
        """POST /internal/llm/parse-resume {text} → {spec, grade_claimed,
        stack, roles, experience_years, about, confidence, notes}.
        Backend обязан обезличить текст до вызова (§3.4)."""
        resp = await self._request(
            "POST", "/internal/llm/parse-resume", json={"text": text}
        )
        return resp.json()

    async def category_ranking(self, spec: str, grade: str) -> list[dict]:
        """GET /internal/category/{spec}/{grade}/ranking → ранжированная
        категория (для «места в ранжировании» в ЛК кандидата)."""
        resp = await self._request(
            "GET", f"/internal/category/{spec}/{grade}/ranking"
        )
        return resp.json()


_client: CoreClient | None = None


def get_core_client() -> CoreClient:
    global _client
    if _client is None:
        _client = CoreClient()
    return _client


CoreDep = Annotated[CoreClient, Depends(get_core_client)]
