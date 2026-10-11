"""Сервис разбора резюме в черновик профиля (PRD §7.10).

Backend передаёт уже обезличенный текст (ПДн в core не попадают, §4.2);
если email-паттерн всё-таки виден — мягкий warning в лог, без отказа.
Два пути, как в app/llm_parse: LLM (строгий JSON, валидация, нормализация,
confidence 0.8+) и детерминированный keyword-fallback (≤0.35). Любая ошибка
LLM → fallback, никогда не 500. Общий keyword/JSON-код — app/llm_parse/common.py.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.llm_parse.common import (
    canon_techs,
    extract_json_object,
    fallback_grade,
    fallback_spec,
    marker_re,
    norm_stack_items,
    valid_grade,
    valid_spec,
)
from app.resume_parse.schemas import ParseResumeOut
from engine.catalog import GRADES, SPECIALIZATIONS
from llm.client import LLMClient

logger = logging.getLogger("app.resume_parse")

LLM_TIMEOUT_S = 20.0
CONFIDENCE_LLM_BASE = 0.8
CONFIDENCE_FALLBACK = 0.35
CONFIDENCE_NOTHING_FOUND = 0.2
ABOUT_MAX_LEN = 500
MAX_ROLES = 8

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:лет|года|год)\b")

# Роль → маркеры (префиксный матч для склонений)
_ROLE_MARKERS: dict[str, tuple[str, ...]] = {
    "backend-разработчик": ("backend-разработчик", "backend разработчик",
                            "backend developer", "бэкенд-разработчик",
                            "бэкенд разработчик", "backend-инженер", "бэкенд-инженер"),
    "frontend-разработчик": ("frontend-разработчик", "frontend разработчик",
                             "frontend developer", "фронтенд-разработчик",
                             "фронтенд разработчик", "frontend-инженер"),
    "fullstack-разработчик": ("fullstack", "full-stack", "фулстек", "фуллстек"),
    "мобильный разработчик": ("мобильный разработчик", "android-разработчик",
                              "ios-разработчик", "mobile developer"),
    "qa-инженер": ("qa-инженер", "qa engineer", "тестировщик",
                   "инженер по тестированию", "qa-специалист"),
    "devops-инженер": ("devops-инженер", "devops", "девопс-инженер", "sre-инженер"),
    "data scientist": ("data scientist", "ml-инженер", "ml engineer",
                       "аналитик данных", "дата-саентист"),
    "системный аналитик": ("системный аналитик", "бизнес-аналитик"),
    "тимлид": ("тимлид", "team lead", "teamlead", "техлид", "руководитель группы"),
    "архитектор": ("архитектор", "solution architect"),
}


def _fallback_roles(text: str) -> list[str]:
    out: list[str] = []
    for role, markers in _ROLE_MARKERS.items():
        if any(re.search(marker_re(m), text) for m in markers):
            out.append(role)
        if len(out) >= MAX_ROLES:
            break
    return out


def _fallback_years(text: str) -> int | None:
    """Максимум из «N лет/года опыта» в тексте, в разумных границах."""
    years = [int(m) for m in _YEARS_RE.findall(text) if 0 <= int(m) <= 40]
    return max(years) if years else None


def _years_to_grade(years: int | None) -> str | None:
    """Подсказка грейда по стажу, если маркеров в тексте нет (PRD §7.2: допустимо)."""
    if years is None:
        return None
    if years < 1:
        return "intern"
    if years < 2:
        return "junior"
    if years < 4:
        return "middle"
    return "senior"


def _fallback_about(text: str) -> str | None:
    """Первый осмысленный абзац (≥40 символов), усечённый до 500."""
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if len(para) >= 40:
            return para[:ABOUT_MAX_LEN]
    return None


def parse_resume_fallback(text: str, reason: str) -> ParseResumeOut:
    lowered = text.lower()
    spec = fallback_spec(lowered)
    years = _fallback_years(lowered)
    grade = fallback_grade(lowered) or _years_to_grade(years)
    roles = _fallback_roles(lowered)
    stack = canon_techs(lowered)
    about = _fallback_about(text)
    confidence = CONFIDENCE_FALLBACK if (spec or grade or stack) else CONFIDENCE_NOTHING_FOUND
    notes = (
        f"эвристика без LLM (keyword-правила по каталогу; {reason}); "
        "рекомендуется проверить распознанное вручную"
    )
    return ParseResumeOut(
        spec=spec, grade_claimed=grade, stack=stack, roles=roles,
        experience_years=years, about=about, confidence=confidence, notes=notes,
    )


# ---------------------------------------------------------------------------
# LLM-путь


class _LLMResumeRaw(BaseModel):
    spec: Any = None
    grade_claimed: Any = None
    stack: list[Any] = Field(default_factory=list)
    roles: list[Any] = Field(default_factory=list)
    experience_years: Any = None
    about: Any = None


_PROMPT_SYSTEM = """Ты парсер резюме ИТ-специалистов. Извлеки черновик профиля из текста резюме
и ответь СТРОГО одним JSON-объектом без пояснений:
{{"spec": <slug|null>, "grade_claimed": <slug|null>, "stack": [<технологии>],
  "roles": [<роли/позиции>], "experience_years": <int|null>, "about": "<текст, ≤500 символов>"}}

Допустимые spec: {specs}.
Допустимые grade: {grades}.
grade_claimed — уровень, ЗАЯВЛЯЕМЫЙ в резюме (не подтверждённый тестом).
stack — технологии нижним регистром, канонические имена: postgresql (не postgres/pg),
kubernetes (не k8s), nextjs (не next.js), typescript (не ts).
roles — позиции из резюме («backend-разработчик», «тимлид»), до 8 штук.
experience_years — полных лет опыта (int) или null.
about — краткая выжимка «о себе» из текста, ≤500 символов, БЕЗ контактов и ПДн."""


def _norm_roles(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        role = re.sub(r"\s+", " ", item.strip().lower())
        if role and role not in out:
            out.append(role)
    return out[:MAX_ROLES]


def _norm_years(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        years = int(value)
        return years if 0 <= years <= 45 else None
    if isinstance(value, str):
        match = re.search(r"\d{1,2}", value)
        if match:
            years = int(match.group())
            return years if 0 <= years <= 45 else None
    return None


def _parse_with_llm(text: str, client: LLMClient) -> ParseResumeOut:
    specs = ", ".join(f"{s.slug} «{s.title}»" for s in SPECIALIZATIONS)
    grades = ", ".join(f"{g.slug} «{g.title}»" for g in GRADES)
    answer = client.chat(
        [
            {"role": "system", "content": _PROMPT_SYSTEM.format(specs=specs, grades=grades)},
            {"role": "user", "content": text},
        ],
        temperature=0.1,
        max_tokens=1000,
    )
    raw = _LLMResumeRaw.model_validate(extract_json_object(answer))
    spec = valid_spec(raw.spec)
    grade = valid_grade(raw.grade_claimed)
    about = raw.about.strip()[:ABOUT_MAX_LEN] if isinstance(raw.about, str) else None
    if about == "":
        about = None
    confidence = (
        CONFIDENCE_LLM_BASE + 0.05 * (spec is not None) + 0.05 * (grade is not None)
    )
    return ParseResumeOut(
        spec=spec,
        grade_claimed=grade,
        stack=norm_stack_items(raw.stack),
        roles=_norm_roles(raw.roles),
        experience_years=_norm_years(raw.experience_years),
        about=about,
        confidence=confidence,
        notes=f"распознано LLM ({client.model})",
    )


def parse_resume(text: str, client: LLMClient | None = None) -> ParseResumeOut:
    """Разбор резюме; любая ошибка LLM → детерминированный fallback.

    Sync (LLMClient — sync httpx): из async-роутера вызывать через
    run_in_threadpool.
    """
    if _EMAIL_RE.search(text):
        logger.warning(
            "parse-resume: похоже на email в тексте — backend обязан обезличивать "
            "(§4.2); запрос не отклонён"
        )
    client = client or LLMClient(timeout=LLM_TIMEOUT_S)
    if not client.available:
        return parse_resume_fallback(text, "нет OPENROUTER_API_KEY")
    try:
        return _parse_with_llm(text, client)
    except (ValidationError, ValueError, KeyError) as e:
        logger.warning("LLM parse-resume: не удалось разобрать ответ (%r) → fallback", e)
        return parse_resume_fallback(text, "неразборчивый ответ LLM")
    except Exception as e:
        logger.warning("LLM parse-resume: ошибка вызова (%r) → fallback", e)
        return parse_resume_fallback(text, "LLM недоступна")
