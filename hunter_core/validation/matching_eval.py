"""Оценка релевантности подбора (PRD §9.2.5, порог §9.3: Precision@5 ≥ 0.8).

Датасетов нет — генерируем синтетику и размечаем программно (описание
разметки — в отчёте): 50 кандидатов (spec, grade, θ, правдоподобный стек,
FSP-история 60/40) и 20 потребностей. Кандидат релевантен потребности,
если spec совпал И грейд ≥ требуемого И stack_overlap ≥ 0.5. Фильтры
работодателя (spec, грейд) применяются до скоринга (PRD §7.5.2), далее
match_score ранжирует → Precision@5, nDCG@10.
"""

from __future__ import annotations

import json
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from engine.catalog import GRADES, grade_index
from engine.scoring import fsp_score, match_score

EVAL_SPECS = ("backend", "frontend", "qa")

# Стеки по специализациям, от популярных к редким (правдоподобные комбинации).
STACK_POOLS: dict[str, tuple[str, ...]] = {
    "backend": ("python", "postgresql", "docker", "fastapi", "redis", "sql",
                "linux", "kafka", "celery", "django", "rabbitmq", "grpc"),
    "frontend": ("javascript", "typescript", "react", "css", "html", "redux",
                 "vite", "nextjs", "webpack", "jest", "tailwind"),
    "qa": ("python", "pytest", "sql", "selenium", "playwright", "postman",
           "jenkins", "allure", "docker", "java", "git"),
}

# Вероятности включения i-го навыка пула в стек кандидата (по убыванию).
_STACK_P = (0.9, 0.8, 0.7, 0.6, 0.5, 0.45, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1)

_GRADE_WEIGHTS = (0.10, 0.30, 0.40, 0.20)  # intern, junior, middle, senior
_NEED_GRADE_WEIGHTS = (0.0, 0.45, 0.40, 0.15)  # потребности: junior/middle чаще
_FSP_RESULTS = ("winner", "diploma", "prize", "participant")
_FSP_RESULT_W = (0.10, 0.25, 0.30, 0.35)

# Масштаб богатства стека по грейду: сеньор в среднем несёт больше навыков.
_STACK_SCALE = (0.7, 1.0, 1.15, 1.3)

THRESH_PRECISION5 = 0.8
STACK_OVERLAP_MIN = 0.5
MIN_POOL = 6  # минимальный пул после фильтров, чтобы Precision@5 была определена


def _weighted_choice(rng: random.Random, items: tuple, weights: tuple[float, ...]) -> Any:
    return rng.choices(items, weights=weights, k=1)[0]


def gen_candidates(n: int, rng: random.Random, now: datetime) -> list[dict[str, Any]]:
    candidates = []
    for i in range(n):
        spec = EVAL_SPECS[i % len(EVAL_SPECS)]
        grade_idx = _weighted_choice(rng, tuple(range(4)), _GRADE_WEIGHTS)
        grade = GRADES[grade_idx]
        lo = max(grade.lo, -2.5)
        hi = min(grade.hi, 3.5)
        theta_true = rng.uniform(lo + 0.05, hi - 0.05)
        pool = STACK_POOLS[spec]
        scale = _STACK_SCALE[grade_idx]
        stack = sorted(
            {pool[j] for j in range(len(pool))
             if rng.random() < min(0.95, _STACK_P[min(j, len(_STACK_P) - 1)] * scale)}
        )
        if not stack or stack[0] != pool[0]:
            stack = sorted(set(stack) | {pool[0]})
        has_fsp = rng.random() < 0.6
        contests = (
            [_weighted_choice(rng, _FSP_RESULTS, _FSP_RESULT_W)
             for _ in range(rng.randint(1, 3))]
            if has_fsp else []
        )
        events = [{"name": f"event-{e}"} for e in range(rng.randint(0, 4))] if has_fsp else []
        days_ago = min(120, int(rng.expovariate(1 / 25)))
        candidates.append(
            {
                "id": f"cand-{i:03d}",
                "spec": spec,
                "grade": grade.slug,
                "theta": round(theta_true, 3),
                "verified": rng.random() < 0.8,
                "stack": stack,
                "fsp_score": round(fsp_score(contests, events), 4),
                "last_active_at": (now - timedelta(days=days_ago)).isoformat(),
            }
        )
    return candidates


def _pool(need: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        c for c in candidates
        if c["spec"] == need["spec"] and grade_index(c["grade"]) >= grade_index(need["grade"])
    ]


def gen_needs(m: int, rng: random.Random, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Генерирует потребности; пересэмплирует те, чей пул после фильтров < MIN_POOL
    (иначе Precision@5 структурно занижена — топ-5 просто не набирается)."""
    needs = []
    for i in range(m):
        need: dict[str, Any] | None = None
        for _ in range(60):
            spec = EVAL_SPECS[i % len(EVAL_SPECS)]
            grade_idx = _weighted_choice(rng, tuple(range(4)), _NEED_GRADE_WEIGHTS)
            pool_names = STACK_POOLS[spec]
            popular = list(pool_names[:5])
            rest = list(pool_names[5:])
            cand: dict[str, Any] = {
                "id": f"need-{i:03d}",
                "spec": spec,
                "grade": GRADES[grade_idx].slug,
                "stack_must": rng.sample(popular, k=min(len(popular), rng.randint(2, 3))),
                "stack_nice": rng.sample(rest, k=min(len(rest), rng.randint(2, 3))),
            }
            if len(_pool(cand, candidates)) >= MIN_POOL:
                need = cand
                break
        if need is None:  # детерминированный запасной вариант: широкий junior-запрос
            spec = EVAL_SPECS[i % len(EVAL_SPECS)]
            pool_names = STACK_POOLS[spec]
            need = {
                "id": f"need-{i:03d}",
                "spec": spec,
                "grade": "junior",
                "stack_must": list(pool_names[:2]),
                "stack_nice": list(pool_names[2:4]),
            }
        needs.append(need)
    return needs


def stack_overlap(candidate: dict[str, Any], need: dict[str, Any]) -> float:
    want = {s.lower() for s in need["stack_must"] + need["stack_nice"]}
    if not want:
        return 0.0
    have = {s.lower() for s in candidate["stack"]}
    return len(want & have) / len(want)


def is_relevant(candidate: dict[str, Any], need: dict[str, Any]) -> bool:
    """Программная разметка: spec совпал И грейд ≥ требуемого И overlap ≥ 0.5."""
    return (
        candidate["spec"] == need["spec"]
        and grade_index(candidate["grade"]) >= grade_index(need["grade"])
        and stack_overlap(candidate, need) >= STACK_OVERLAP_MIN
    )


def _dcg(gains: list[int]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def evaluate_need(
    need: dict[str, Any], candidates: list[dict[str, Any]], now: datetime
) -> dict[str, Any]:
    """Фильтры (spec, грейд) → match_score ранжирование → Precision@5, nDCG@10."""
    pool = _pool(need, candidates)
    scored = []
    for c in pool:
        score, explanation = match_score(c, need, now=now)
        scored.append({"candidate": c, "score": score, "explanation": explanation,
                       "relevant": is_relevant(c, need)})
    scored.sort(key=lambda s: (-s["score"], s["candidate"]["id"]))
    top5 = scored[:5]
    top10 = scored[:10]
    n_rel_pool = sum(1 for s in scored if s["relevant"])
    precision5 = sum(1 for s in top5 if s["relevant"]) / 5
    idcg = _dcg([1] * min(10, n_rel_pool))
    ndcg10 = _dcg([1 if s["relevant"] else 0 for s in top10]) / idcg if idcg > 0 else 0.0
    return {
        "need_id": need["id"],
        "spec": need["spec"],
        "grade": need["grade"],
        "pool_size": len(pool),
        "relevant_in_pool": n_rel_pool,
        "precision_at_5": round(precision5, 4),
        "ndcg_at_10": round(ndcg10, 4),
        "top5": [
            {
                "candidate_id": s["candidate"]["id"],
                "score": s["score"],
                "relevant": s["relevant"],
                "grade": s["candidate"]["grade"],
                "verified": s["candidate"]["verified"],
            }
            for s in top5
        ],
        "top1_explanation": scored[0]["explanation"] if scored else [],
    }


def run_matching_eval(
    out_path: str | Path | None = None,
    seed: int = 11,
    n_candidates: int = 50,
    n_needs: int = 20,
) -> dict[str, Any]:
    rng = random.Random(seed)
    now = datetime(2026, 10, 7, tzinfo=UTC)  # фиксированный «сейчас» для воспроизводимости
    candidates = gen_candidates(n_candidates, rng, now)
    needs = gen_needs(n_needs, rng, candidates)
    per_need = [evaluate_need(need, candidates, now) for need in needs]
    valid = [r for r in per_need if r["pool_size"] > 0]
    precision5 = sum(r["precision_at_5"] for r in valid) / len(valid) if valid else 0.0
    ndcg10 = sum(r["ndcg_at_10"] for r in valid) / len(valid) if valid else 0.0
    report: dict[str, Any] = {
        "params": {
            "seed": seed,
            "n_candidates": n_candidates,
            "n_needs": n_needs,
            "relevance_rule": "spec совпал И grade >= требуемого И stack_overlap >= 0.5",
            "stack_overlap_min": STACK_OVERLAP_MIN,
        },
        "metrics": {
            "precision_at_5": round(precision5, 4),
            "ndcg_at_10": round(ndcg10, 4),
            "needs_evaluated": len(valid),
        },
        "threshold": {"precision_at_5 >= ": THRESH_PRECISION5},
        "overall_pass": precision5 >= THRESH_PRECISION5,
        "per_need": per_need,
    }
    if out_path is not None:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
