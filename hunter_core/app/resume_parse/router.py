"""Роутер разбора резюме (контракт: POST /internal/llm/parse-resume)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.resume_parse import service
from app.resume_parse.schemas import ParseResumeIn, ParseResumeOut

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post(
    "/parse-resume",
    response_model=ParseResumeOut,
    summary="Разбор обезличенного текста резюме в черновик профиля "
    "(LLM OpenRouter; при недоступности — keyword-fallback, PRD §7.10)",
)
async def parse_resume(payload: ParseResumeIn) -> ParseResumeOut:
    return await run_in_threadpool(service.parse_resume, payload.text)
