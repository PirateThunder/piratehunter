"""Общие хелперы LLM/keyword-парсеров (llm_parse, resume_parse).

Словари keyword-правил по каталогу, извлечение JSON из ответа модели,
нормализация технологий (алиасы), валидация spec/grade slug'ов.
"""

from __future__ import annotations

import json
import re
from typing import Any

from engine.catalog import SPECIALIZATIONS, get_grade, get_specialization

MAX_STACK_ITEMS = 12

# Явные маркеры специализации (вес ×3 — сильнее отдельной технологии)
SPEC_STRONG_MARKERS: dict[str, tuple[str, ...]] = {
    "backend": ("backend", "бэкенд"),
    "frontend": ("frontend", "фронтенд", "фронтэнд"),
    "fullstack": ("fullstack", "full-stack", "фулстек", "фуллстек"),
    "mobile": ("mobile", "мобильн"),
    "qa": ("qa", "тестировщик", "тестирование", "quality assurance", "автотест"),
    "devops": ("devops", "девопс", "sre", "инфраструктур"),
    "data-ml": ("data science", "machine learning", "машинное обучение", "ml",
                "data-ml", "нейросет"),
}

# Технология → (специализации, которым она голосует) — по темам каталога
TECH_SPECS: dict[str, tuple[str, ...]] = {
    "python": ("backend", "qa", "data-ml"),
    "fastapi": ("backend",), "django": ("backend",), "flask": ("backend",),
    "postgresql": ("backend",), "mysql": ("backend",), "redis": ("backend",),
    "kafka": ("backend",), "rabbitmq": ("backend",), "celery": ("backend",),
    "grpc": ("backend",), "graphql": ("backend", "frontend"), "golang": ("backend",),
    "java": ("backend",), "spring": ("backend",), "nodejs": ("backend", "frontend"),
    "sql": ("backend", "qa", "data-ml"), "clickhouse": ("data-ml", "backend"),
    "mongodb": ("backend",), "elasticsearch": ("backend",),
    "react": ("frontend",), "vue": ("frontend",), "angular": ("frontend",),
    "svelte": ("frontend",), "nextjs": ("frontend",), "typescript": ("frontend",),
    "javascript": ("frontend",), "redux": ("frontend",), "vite": ("frontend",),
    "webpack": ("frontend",), "jest": ("frontend",), "css": ("frontend",),
    "html": ("frontend",),
    "kotlin": ("mobile",), "swift": ("mobile",), "flutter": ("mobile",),
    "android": ("mobile",), "ios": ("mobile",),
    "pytest": ("qa",), "selenium": ("qa",), "playwright": ("qa",),
    "postman": ("qa",), "allure": ("qa",), "junit": ("qa",),
    "docker": ("devops", "backend"), "kubernetes": ("devops",),
    "terraform": ("devops",), "ansible": ("devops",), "nginx": ("devops",),
    "linux": ("devops",), "jenkins": ("devops", "qa"),
    "pandas": ("data-ml",), "numpy": ("data-ml",), "pytorch": ("data-ml",),
    "tensorflow": ("data-ml",), "sklearn": ("data-ml",), "airflow": ("data-ml",),
    "spark": ("data-ml",),
}

# Алиасы технологий → каноническое имя
TECH_ALIASES: dict[str, str] = {
    "postgres": "postgresql", "pg": "postgresql", "next.js": "nextjs",
    "next": "nextjs", "node": "nodejs", "node.js": "nodejs", "ts": "typescript",
    "js": "javascript", "k8s": "kubernetes", "scikit-learn": "sklearn",
    "mongo": "mongodb", "rabbit": "rabbitmq", "go": "golang",
}

GRADE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("senior", ("senior", "сеньор", "синьор", "сениор", "lead", "лид")),
    ("middle", ("middle", "мидл", "миддл", "medior")),
    ("junior", ("junior", "джуниор", "джун")),
    ("intern", ("intern", "стажёр", "стажер", "практикант", "начинающ")),
)

NICE_SPLIT_RE = re.compile(
    r"желательно|будет плюсом|плюсом|nice to have|необязательно|не обязательно"
)


def marker_re(m: str) -> str:
    """Маркер-префикс (русские слова склоняются); короткие латинские — строго."""
    if len(m) <= 2 and m.isascii():
        return rf"(?<![\w-]){re.escape(m)}(?![\w-])"
    return rf"(?<![\w-]){re.escape(m)}"


def find_tech_hits(text: str) -> list[tuple[str, int, int]]:
    """(канон, start, end) каждого вхождения технологии, по порядку в тексте.

    Точка в конце предложения не мешает («k8s.»); пересекающиеся вхождения
    («next» внутри «next.js») отбрасываются в пользу более длинного имени.
    """
    vocab = {**{t: t for t in TECH_SPECS}, **TECH_ALIASES}
    raw: list[tuple[str, int, int]] = []
    for name in sorted(vocab, key=len, reverse=True):
        for m in re.finditer(rf"(?<![\w.]){re.escape(name)}(?!\w)", text):
            canon = vocab[name]
            if canon in TECH_SPECS:
                raw.append((canon, m.start(), m.end()))
    raw.sort(key=lambda h: (h[1], -(h[2] - h[1])))
    hits: list[tuple[str, int, int]] = []
    for hit in raw:
        if any(hit[1] < acc_end and hit[2] > acc_start for _c, acc_start, acc_end in hits):
            continue
        hits.append(hit)
    hits.sort(key=lambda h: h[1])
    return hits


def canon_techs(text: str) -> list[str]:
    """Технологии в тексте (канонические имена, порядок первого входа)."""
    found: list[str] = []
    for canon, _start, _end in find_tech_hits(text):
        if canon not in found:
            found.append(canon)
    return found


def fallback_spec(text: str) -> str | None:
    scores = {s.slug: 0 for s in SPECIALIZATIONS}
    for slug, markers in SPEC_STRONG_MARKERS.items():
        if any(re.search(marker_re(m), text) for m in markers):
            scores[slug] += 3
    for tech in canon_techs(text):
        for slug in TECH_SPECS[tech]:
            scores[slug] += 1
    best = max(scores, key=lambda s: (scores[s], -list(scores).index(s)))
    return best if scores[best] > 0 else None


def fallback_grade(text: str) -> str | None:
    best: tuple[int, str] | None = None
    for slug, markers in GRADE_MARKERS:
        for m in markers:
            match = re.search(marker_re(m), text)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), slug)
    return best[1] if best else None


def extract_json_object(text: str) -> dict[str, Any]:
    """Достаёт JSON-объект из ответа модели (```-fences или лишний текст)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    if start < 0:
        raise ValueError("в ответе модели нет JSON-объекта")
    obj, _end = json.JSONDecoder().raw_decode(candidate[start:])
    if not isinstance(obj, dict):
        raise ValueError("ответ модели — не JSON-объект")
    return obj


def norm_stack_items(items: list[Any]) -> list[str]:
    """Нормализация технологий: нижний регистр, алиасы, дедупликация, лимит."""
    out: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        canon = TECH_ALIASES.get(item.strip().lower(), item.strip().lower())
        canon = re.sub(r"\s+", " ", canon)
        if canon and canon not in out:
            out.append(canon)
    return out[:MAX_STACK_ITEMS]


def valid_spec(value: Any) -> str | None:
    """Невалидный spec от LLM отбрасывается в null."""
    if not isinstance(value, str) or not value.strip():
        return None
    slug = value.strip().lower()
    try:
        get_specialization(slug)
    except ValueError:
        return None
    return slug


def valid_grade(value: Any) -> str | None:
    """Невалидный grade от LLM отбрасывается в null."""
    if not isinstance(value, str) or not value.strip():
        return None
    slug = value.strip().lower()
    try:
        get_grade(slug)
    except ValueError:
        return None
    return slug
