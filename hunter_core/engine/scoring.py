"""Скоринг и матчинг (PRD §7.5.2, §7.9).

score = 0.40·test_score + 0.30·stack_match + 0.20·fsp_score + 0.10·freshness

test_score — позиция θ в полосе грейда; unverified — срезанный потолок 0.4
(показываем со статусом «не подтверждён» и опускаем, не скрываем).
stack_match — Σ w(совпавший навык), must ×3, нормировка к 0..1.
fsp_score — §7.9: победитель 1.0 / диплом I–III 0.7 / призовое 0.5 /
участие 0.15 / мероприятие 0.05; явки с затуханием ×0.5^(i−1); cap 1.0.
freshness — exp-decay от последней активности, полураспад 30 дней.
match_score возвращает (score, explanation) — разложение по факторам для
панели «Почему в подборке» (PRD §7.5.3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from engine.catalog import get_grade

DEFAULT_WEIGHTS: dict[str, float] = {
    "test": 0.40,
    "stack": 0.30,
    "fsp": 0.20,
    "freshness": 0.10,
}

UNVERIFIED_CAP = 0.4  # потолок test_score для неподтверждённого грейда

FSP_RESULT_WEIGHTS = {"winner": 1.0, "diploma": 0.7, "prize": 0.5, "participant": 0.15}
FSP_EVENT_WEIGHT = 0.05
FSP_DECAY = 0.5  # множитель затухания за i-ю явку: ×0.5^(i−1)
FSP_CAP = 1.0

FRESHNESS_HALF_LIFE_DAYS = 30.0


def test_score(theta: float, grade: str, verified: bool = True) -> float:
    """Позиция θ внутри полосы грейда (0..1); unverified — потолок 0.4."""
    g = get_grade(grade)
    pos = (theta - g.lo) / (g.hi - g.lo)
    pos = min(1.0, max(0.0, pos))
    return pos if verified else min(pos, UNVERIFIED_CAP)


def _entry_kind(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    return str(entry.get("result", entry.get("kind", "participant")))


def fsp_score(
    contests: list[Any] | None = None,
    events: list[Any] | None = None,
) -> float:
    """Счёт достижений ФСП (PRD §7.9), cap 1.0; нет истории → 0.

    contests: записи вида "winner" | "diploma" | "prize" | "participant"
    (или dict с полем result). Результаты (1.0/0.7/0.5) идут в полном весе;
    участия (0.15) и мероприятия (0.05) — с затуханием ×0.5^(i−1) за i-ю
    явку (защита от набивания профиля одними явками). Дисциплины и уровни
    не ранжируем, давность не штрафуем (Q&A 06.10).
    """
    total = 0.0
    attendance = 0
    for entry in contests or []:
        kind = _entry_kind(entry)
        if kind == "participant":
            attendance += 1
            total += FSP_RESULT_WEIGHTS["participant"] * FSP_DECAY ** (attendance - 1)
        elif kind in FSP_RESULT_WEIGHTS:
            total += FSP_RESULT_WEIGHTS[kind]
        else:
            raise ValueError(f"неизвестный тип достижения ФСП: {kind!r}")
    for i, _event in enumerate(events or [], start=1):
        total += FSP_EVENT_WEIGHT * FSP_DECAY ** (i - 1)
    return min(FSP_CAP, total)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _freshness_days(last_active_at: Any, now: Any = None) -> float | None:
    last = _parse_dt(last_active_at)
    if last is None:
        return None
    moment = _parse_dt(now) or datetime.now(UTC)
    return (moment - last).total_seconds() / 86400.0


def freshness(last_active_at: Any, now: Any = None) -> float:
    """exp-decay, полураспад 30 дней; None (нет активности) → 0.0."""
    days = _freshness_days(last_active_at, now)
    if days is None:
        return 0.0
    if days <= 0:
        return 1.0
    return 0.5 ** (days / FRESHNESS_HALF_LIFE_DAYS)


def _norm_tags(tags: Any) -> set[str]:
    return {str(t).strip().lower() for t in tags or [] if str(t).strip()}


def stack_match(candidate_stack: Any, must: Any, nice: Any) -> float:
    """Σ w(совпавший навык): must ×3, nice ×1; нормировка к 0..1.

    Совпадения регистронезависимы; пересечение must∩nice считается как must.
    Пустые требования → 0.0 (нет сигнала).
    """
    have = _norm_tags(candidate_stack)
    must_set = _norm_tags(must)
    nice_set = _norm_tags(nice) - must_set
    denom = 3 * len(must_set) + len(nice_set)
    if denom == 0:
        return 0.0
    hits = 3 * len(must_set & have) + len(nice_set & have)
    return hits / denom


def match_score(
    snapshot: dict[str, Any],
    need: dict[str, Any],
    weights: dict[str, float] | None = None,
    now: Any = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Взвешенный скоринг кандидата под потребность + объяснение по факторам.

    snapshot: {theta, grade, verified, fsp_score, stack, last_active_at}
    (test_score можно передать готовым — тогда используется он).
    need: {stack_must, stack_nice} (+ spec/grade — фильтры применяются до
    скоринга вызывающей стороной, PRD §7.5.2).
    explanation: [{factor, weight, value, contribution, human_text}] по всем
    4 факторам в порядке весов — для панели «Почему в подборке».
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    theta = float(snapshot.get("theta", 0.0))
    grade = str(snapshot.get("grade", "intern"))
    verified = bool(snapshot.get("verified", True))
    ts = snapshot.get("test_score")
    ts = float(ts) if ts is not None else test_score(theta, grade, verified)

    must = list(need.get("stack_must", []))
    nice = list(need.get("stack_nice", []))
    sm = stack_match(snapshot.get("stack", []), must, nice)
    have = _norm_tags(snapshot.get("stack", []))
    nice_only = _norm_tags(nice) - _norm_tags(must)
    must_hits = len(_norm_tags(must) & have)
    nice_hits = len(nice_only & have)

    fs = min(1.0, max(0.0, float(snapshot.get("fsp_score", 0.0))))

    fr = freshness(snapshot.get("last_active_at"), now)
    days = _freshness_days(snapshot.get("last_active_at"), now)

    grade_note = "" if verified else " (не подтверждён — потолок 0.4)"
    fsp_note = "нет истории ФСП" if fs == 0.0 else f"суммарный счёт {fs:.2f}"
    if days is None:
        fresh_note = "нет данных об активности"
    else:
        fresh_note = f"активность {max(0, round(days))} дн. назад"

    explanation = [
        {
            "factor": "test",
            "weight": w["test"],
            "value": round(ts, 4),
            "contribution": round(w["test"] * ts, 4),
            "human_text": f"тест: грейд {grade}{grade_note}, θ={theta:.2f} → {ts:.2f}",
        },
        {
            "factor": "stack",
            "weight": w["stack"],
            "value": round(sm, 4),
            "contribution": round(w["stack"] * sm, 4),
            "human_text": (
                f"стек: совпало must {must_hits}/{len(_norm_tags(must))}, "
                f"nice {nice_hits}/{len(nice_only)} → {sm:.2f}"
            ),
        },
        {
            "factor": "fsp",
            "weight": w["fsp"],
            "value": round(fs, 4),
            "contribution": round(w["fsp"] * fs, 4),
            "human_text": f"достижения ФСП: {fsp_note}",
        },
        {
            "factor": "freshness",
            "weight": w["freshness"],
            "value": round(fr, 4),
            "contribution": round(w["freshness"] * fr, 4),
            "human_text": f"свежесть профиля: {fresh_note} → {fr:.2f}",
        },
    ]
    total = sum(e["contribution"] for e in explanation)
    return round(min(1.0, max(0.0, total)), 4), explanation
