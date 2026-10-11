"""Роутер LLM-парсинга потребности (контракт: POST /internal/llm/parse-need)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.llm_parse import service
from app.llm_parse.schemas import ParseNeedIn, ParseNeedOut

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post(
    "/parse-need",
    response_model=ParseNeedOut,
    summary="Парсинг потребности работодателя из свободного текста "
    "(LLM OpenRouter; при недоступности — детерминированный keyword-fallback)",
)
async def parse_need(payload: ParseNeedIn) -> ParseNeedOut:
    # service.parse_need sync (LLMClient — sync httpx) → вне event loop
    return await run_in_threadpool(service.parse_need, payload.raw_text)
