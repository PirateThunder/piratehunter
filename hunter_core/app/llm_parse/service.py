"""Сервис парсинга потребности: LLM-путь (OpenRouter) + детерминированный fallback.

LLM получает допустимые slug'и spec/grade из каталога и отвечает строгим
JSON; ответ разбирается устойчиво (```-fences, лишний текст), валидируется
pydantic'ом, невалидные spec/grade отбрасываются в null. Любая ошибка
сети/ключа/парсинга → keyword-fallback (PRD §3.4: система работает без LLM).
Ответ никогда не падает с 500 из-за LLM. Общий keyword/JSON-код — в
app/llm_parse/common.py.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.llm_parse.common import (
    MAX_STACK_ITEMS,
    NICE_SPLIT_RE,
    extract_json_object,
    fallback_grade,
    fallback_spec,
    find_tech_hits,
    norm_stack_items,
    valid_grade,
    valid_spec,
)
from app.llm_parse.schemas import ParseNeedOut
from engine.catalog import GRADES, SPECIALIZATIONS
from llm.client import LLMClient

logger = logging.getLogger("app.llm_parse")

LLM_TIMEOUT_S = 20.0
CONFIDENCE_LLM_BASE = 0.8
CONFIDENCE_FALLBACK = 0.35
CONFIDENCE_NOTHING_FOUND = 0.2


# ---------------------------------------------------------------------------
# Детерминированный fallback


def _fallback_stacks(text: str) -> tuple[list[str], list[str]]:
    """Технологии → must/nice. Nice-зоны: после маркера («желательно X») или
    непосредственно перед ним («X будет плюсом» — русский порядок слов)."""
    markers = [(m.start(), m.end()) for m in NICE_SPLIT_RE.finditer(text)]
    must: list[str] = []
    nice: list[str] = []
    for canon, start, end in find_tech_hits(text):
        is_nice = False
        for m_start, m_end in markers:
            after = start >= m_end
            # «X будет плюсом»: gap без знаков препинания-разделителей (иначе
            # «react и typescript, желательно next.js» — запятая отделяет must)
            just_before = end <= m_start and text[end:m_start].strip() in ("", "и")
            if after or just_before:
                is_nice = True
                break
        target = nice if is_nice else must
        if canon not in target:
            target.append(canon)
    # технология в nice не должна дублироваться в must
    nice = [t for t in nice if t not in must]
    return must[:MAX_STACK_ITEMS], nice[:MAX_STACK_ITEMS]


def parse_need_fallback(raw_text: str, reason: str) -> ParseNeedOut:
    """Keyword-правила по каталогу; честные пониженные confidence и notes."""
    text = raw_text.lower()
    spec = fallback_spec(text)
    grade = fallback_grade(text)
    must, nice = _fallback_stacks(text)
    confidence = CONFIDENCE_FALLBACK if (spec or grade or must) else CONFIDENCE_NOTHING_FOUND
    notes = (
        f"эвристика без LLM (keyword-правила по каталогу; {reason}); "
        "рекомендуется проверить распознанное вручную"
    )
    return ParseNeedOut(spec=spec, grade=grade, stack_must=must, stack_nice=nice,
                        confidence=confidence, notes=notes)


# ---------------------------------------------------------------------------
# LLM-путь


class _LLMNeedRaw(BaseModel):
    spec: Any = None
    grade: Any = None
    stack_must: list[Any] = Field(default_factory=list)
    stack_nice: list[Any] = Field(default_factory=list)
    notes: Any = ""


_PROMPT_SYSTEM = """Ты парсер потребностей работодателя для платформы подбора ИТ-специалистов.
Извлеки структуру из свободного текста и ответь СТРОГО одним JSON-объектом без пояснений:
{{"spec": <slug|null>, "grade": <slug|null>, "stack_must": [<технологии>],
  "stack_nice": [<технологии>], "notes": "<как понял запрос, 1 фраза>"}}

Допустимые spec: {specs}.
Допустимые grade: {grades}.
stack_must — обязательные технологии; stack_nice — желательные («желательно», «будет плюсом»).
Технологии — нижний регистр, канонические имена: postgresql (не postgres/pg), kubernetes (не k8s),
nextjs (не next.js), typescript (не ts). Если spec или grade не определяются — null."""


def _parse_with_llm(raw_text: str, client: LLMClient) -> ParseNeedOut:
    specs = ", ".join(f"{s.slug} «{s.title}»" for s in SPECIALIZATIONS)
    grades = ", ".join(f"{g.slug} «{g.title}»" for g in GRADES)
    answer = client.chat(
        [
            {"role": "system", "content": _PROMPT_SYSTEM.format(specs=specs, grades=grades)},
            {"role": "user", "content": raw_text},
        ],
        temperature=0.1,
        max_tokens=600,
    )
    raw = _LLMNeedRaw.model_validate(extract_json_object(answer))
    spec = valid_spec(raw.spec)
    grade = valid_grade(raw.grade)
    confidence = (
        CONFIDENCE_LLM_BASE + 0.05 * (spec is not None) + 0.05 * (grade is not None)
    )
    notes = raw.notes if isinstance(raw.notes, str) and raw.notes.strip() else (
        f"распознано LLM ({client.model})"
    )
    return ParseNeedOut(
        spec=spec,
        grade=grade,
        stack_must=norm_stack_items(raw.stack_must),
        stack_nice=norm_stack_items(raw.stack_nice),
        confidence=confidence,
        notes=notes.strip(),
    )


def parse_need(raw_text: str, client: LLMClient | None = None) -> ParseNeedOut:
    """Парсинг потребности; любая ошибка LLM → детерминированный fallback.

    Sync (LLMClient — sync httpx): из async-роутера вызывать через
    run_in_threadpool.
    """
    client = client or LLMClient(timeout=LLM_TIMEOUT_S)
    if not client.available:
        return parse_need_fallback(raw_text, "нет OPENROUTER_API_KEY")
    try:
        return _parse_with_llm(raw_text, client)
    except (ValidationError, ValueError, KeyError) as e:
        logger.warning("LLM parse-need: не удалось разобрать ответ (%r) → fallback", e)
        return parse_need_fallback(raw_text, "неразборчивый ответ LLM")
    except Exception as e:
        logger.warning("LLM parse-need: ошибка вызова (%r) → fallback", e)
        return parse_need_fallback(raw_text, "LLM недоступна")
