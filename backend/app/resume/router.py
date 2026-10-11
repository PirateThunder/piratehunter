"""Резюме (§7.10): загрузка PDF → обезличенный LLM-разбор в core →
черновик для ручного review; генерация стандартизированного
PDF-профиля (бренд ФСП, weasyprint)."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Response, UploadFile

from ..auth.dependencies import CandidateUser
from ..candidates import service as candidates_service
from ..core_client.client import CoreDep, CoreError
from ..database import DbDep
from .pdf import (
    MAX_RESUME_BYTES,
    ResumeExtractError,
    extract_text,
    render_profile_pdf,
)
from .sanitize import sanitize_resume_text
from .schemas import ResumeDraft, ResumeDraftOut

logger = logging.getLogger(__name__)

router = APIRouter(tags=["candidate"])

_PARSE_UNAVAILABLE = (
    "разбор резюме временно недоступен — заполните форму вручную"
)


@router.post(
    "/candidate/profile/resume",
    response_model=ResumeDraftOut,
    summary="Загрузить резюме (PDF) → черновик профиля",
    description="PDF → текст (pypdf) → обезличивание (контакты в LLM "
    "не уходят, §3.4) → разбор в core → {draft} для ручного review. "
    "Профиль НЕ перезаписывается. Битый файл → 422; core недоступен → "
    "200 с пустым черновиком.",
)
async def upload_resume(
    user: CandidateUser, core: CoreDep, file: UploadFile
) -> ResumeDraftOut:
    content = await file.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(422, "файл больше 10 МБ")
    try:
        text = extract_text(content)
    except ResumeExtractError as e:
        raise HTTPException(422, str(e)) from e
    clean = sanitize_resume_text(text)
    try:
        parsed = await core.parse_resume(clean)
        draft = ResumeDraft.model_validate(parsed)
    except CoreError:
        logger.warning("parse_resume failed", exc_info=True)
        draft = ResumeDraft(notes=_PARSE_UNAVAILABLE)
    return ResumeDraftOut(draft=draft)


@router.get(
    "/candidate/profile/pdf",
    summary="Скачать стандартизированный PDF-профиль",
    description="Бренд ФСП: категория, подтверждённый грейд, стек, "
    "достижения ФСП. PDF публичен по замыслу — вместо контактов "
    "плашка «контакты скрыты до приглашения».",
)
async def download_profile_pdf(
    user: CandidateUser, session: DbDep
) -> Response:
    profile = await candidates_service.get_profile_or_404(session, user.id)
    grade_state = await candidates_service.get_grade_state(session, user.id)
    pdf = await asyncio.to_thread(render_profile_pdf, profile, user,
                                  grade_state)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="profile.pdf"'
        },
    )
