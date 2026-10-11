"""Сервис матчинга: фильтры до скоринга, затем match_score с explanation.

Контракт §8.2 читает только снапшоты (PRD §4.3) — backend не дёргается.
Вне категории (грейд ниже требуемого или не подтверждён) — блоком «рядом
с запросом» с in_category=false (PRD §7.5.2), без исключения из выдачи.
В режиме категории stack-фактор — нейтральная константа (PRD §7.5.4).
Скоринг — sync-математика, вызывается через run_in_threadpool из роутера.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import NEUTRAL_STACK_VALUE
from app.exceptions import BadRequestError
from app.models import AssessmentSnapshotModel
from engine import scoring
from engine.catalog import get_grade, get_specialization, grade_index
from engine.scoring import DEFAULT_WEIGHTS


def _snapshot_dict(row: AssessmentSnapshotModel) -> dict[str, Any]:
    return {
        "theta": row.theta or 0.0,
        "grade": row.grade_verified or "intern",
        "verified": row.grade_verified is not None,
        "test_score": row.test_score,  # готовый из снапшота (PRD §4.3)
        "stack": row.stack,
        "fsp_score": row.fsp_score,
        "last_active_at": row.updated_at,
    }


def _match_one(row: AssessmentSnapshotModel, need: dict[str, Any]) -> dict[str, Any]:
    score, explanation = scoring.match_score(_snapshot_dict(row), need)
    return {"candidate_id": row.candidate_id, "score": score,
            "explanation": explanation, "in_category": True}


def rank_match_sync(
    snapshots: list[AssessmentSnapshotModel], need: dict[str, Any]
) -> list[dict[str, Any]]:
    """Фильтры (spec, grade) → match_score → категория, затем «рядом с запросом»."""
    try:
        get_specialization(need["spec"])
        if need.get("grade"):
            get_grade(need["grade"])
    except ValueError as e:
        raise BadRequestError(str(e)) from e
    spec_pool = [s for s in snapshots if s.spec_slug == need["spec"]]
    need_grade_idx = grade_index(need["grade"]) if need.get("grade") else None

    def in_category(s: AssessmentSnapshotModel) -> bool:
        if s.grade_verified is None:
            return False  # неподтверждённые — «рядом», с потолком test_score
        return need_grade_idx is None or grade_index(s.grade_verified) >= need_grade_idx

    core = [_match_one(s, need) for s in spec_pool if in_category(s)]
    near = [_match_one(s, need) for s in spec_pool if not in_category(s)]
    for item in near:
        item["in_category"] = False
    core.sort(key=lambda i: (-i["score"], i["candidate_id"]))
    near.sort(key=lambda i: (-i["score"], i["candidate_id"]))
    return (core + near)[: int(need.get("limit", 20))]


def rank_category_sync(
    snapshots: list[AssessmentSnapshotModel], spec: str, grade: str
) -> list[dict[str, Any]]:
    """Ранжирование внутри категории (PRD §7.5.4): stack — нейтральная константа."""
    try:
        get_specialization(spec)
        get_grade(grade)
    except ValueError as e:
        raise BadRequestError(str(e)) from e
    w = DEFAULT_WEIGHTS
    out = []
    for row in snapshots:
        if row.spec_slug != spec or row.grade_verified != grade:
            continue
        # None → формула из theta (§7.5.2), готовое значение — из снапшота
        ts_raw = row.test_score
        ts = min(1.0, max(0.0, ts_raw)) if ts_raw is not None else scoring.test_score(
            row.theta or 0.0, grade, verified=True
        )
        fs = min(1.0, max(0.0, row.fsp_score))
        fr = scoring.freshness(row.updated_at)
        explanation = [
            {"factor": "test", "weight": w["test"], "value": round(ts, 4),
             "contribution": round(w["test"] * ts, 4),
             "human_text": (
                 f"тест: грейд {grade} подтверждён, "
                 f"θ={(row.theta or 0.0):.2f} → {ts:.2f}"
             )},
            {"factor": "stack", "weight": w["stack"], "value": NEUTRAL_STACK_VALUE,
             "contribution": round(w["stack"] * NEUTRAL_STACK_VALUE, 4),
             "human_text": "стек: нейтральная константа (режим категории, PRD §7.5.4)"},
            {"factor": "fsp", "weight": w["fsp"], "value": round(fs, 4),
             "contribution": round(w["fsp"] * fs, 4),
             "human_text": f"достижения ФСП → {fs:.2f}"},
            {"factor": "freshness", "weight": w["freshness"], "value": round(fr, 4),
             "contribution": round(w["freshness"] * fr, 4),
             "human_text": f"свежесть профиля → {fr:.2f}"},
        ]
        score = round(min(1.0, sum(e["contribution"] for e in explanation)), 4)
        out.append({"candidate_id": row.candidate_id, "score": score,
                    "explanation": explanation, "in_category": True})
    out.sort(key=lambda i: (-i["score"], i["candidate_id"]))
    return out


async def list_snapshots(
    db: AsyncSession, spec: str | None = None
) -> list[AssessmentSnapshotModel]:
    q = select(AssessmentSnapshotModel)
    if spec:
        q = q.where(AssessmentSnapshotModel.spec_slug == spec)
    return list((await db.execute(q)).scalars())
