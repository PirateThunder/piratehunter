"""Извлечение текста из PDF (pypdf) и генерация PDF-профиля
(Jinja2 + weasyprint, айдентика ФСП §3.3)."""

import io
from datetime import datetime
from pathlib import Path

import jinja2
from pypdf import PdfReader

from ..candidates.models import CandidateProfile, GradeState
from ..constants import GRADES, SPECIALIZATION_TITLES
from ..users.models import User

MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 МБ

_TEMPLATES = Path(__file__).parent / "templates"
_jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_TEMPLATES), autoescape=True
)


class ResumeExtractError(Exception):
    """Битый/не-PDF файл или пустой текст (→ 422)."""


def extract_text(content: bytes) -> str:
    """Текст всех страниц PDF; ошибки парсинга и пустой текст —
    ResumeExtractError."""
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        raise ResumeExtractError(
            "не удалось прочитать файл как PDF — проверьте, что это "
            "валидный PDF-документ"
        ) from e
    if not text.strip():
        raise ResumeExtractError(
            "в PDF не найден текст — возможно, это скан; загрузите "
            "текстовый PDF или заполните форму вручную"
        )
    return text.strip()


def render_profile_pdf(
    profile: CandidateProfile,
    user: User,
    grade_state: GradeState | None,
) -> bytes:
    """Стандартизированный PDF-профиль (бренд ФСП). Публичный по
    замыслу: контактов в нём нет — плашка «контакты скрыты до
    приглашения» (§7.10)."""
    template = _jinja.get_template("resume_pdf.html")
    grade_verified = grade_state.grade_verified if grade_state else None
    fsp = profile.fsp_data or {}
    html = template.render(
        fio=profile.fio,
        spec_slug=profile.spec_slug,
        spec_title=SPECIALIZATION_TITLES.get(
            profile.spec_slug or "", profile.spec_slug or "—"
        ),
        grade_verified=grade_verified,
        grade_claimed=profile.grade_claimed,
        grades=GRADES,
        stack=list(profile.stack or []),
        roles=list(profile.roles or []),
        experience_years=profile.experience_years,
        about=profile.about,
        has_fsp=profile.fsp_data is not None,
        fsp_rating=fsp.get("rating"),
        fsp_contests=[
            c for c in (fsp.get("contests") or [])
            if c.get("place") is not None or c.get("diploma")
        ][:8],
        generated_at=datetime.now().strftime("%d.%m.%Y"),
    )
    from weasyprint import HTML  # импорт по месту: тянет pango

    return HTML(string=html).write_pdf()
