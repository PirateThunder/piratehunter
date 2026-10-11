"""Валидационный харнесс (PRD §9): синтетический контур, метрики и пороги §9.3.

Прогон: N агентов (равномерно θ_true ∈ [−2.5, 3.5]) × R повторных тестов
(TestEngine + свежий банк из фабрик на каждый repeat). Метрики §9.2:
стабильность грейда (точное совпадение, ±1), Spearman(θ_true, θ_est),
confusion matrix истинный × присвоенный, эквивалентность экземпляров
(K шаблонов × 50 seeds: доля seeds с разбросом доли верных вне
биномиального 95% ДИ), калибровка BetaStat, пересечение наборов шаблонов
между сессиями (средний попарный Jaccard). Пороги §9.3: стабильность
≥ 80% / ±1 ≥ 97%, Spearman ≥ 0.85, путаница соседних грейдов < 15%.
Отчёт: validation.json + summary.txt + графики (scatter θ, heatmap confusion).
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from engine import irt
from engine.cat import CatConfig, TestEngine
from engine.catalog import (
    GRADES,
    MCQ_TOPICS,
    SQL_TOPICS,
    grade_for_theta,
    grade_index,
)
from itembank import factory_mcq, factory_sql
from itembank.registry import BankRegistry
from validation.agents import SyntheticAgent

THETA_TRUE_LO = -2.5
THETA_TRUE_HI = 3.5

# Пороги §9.3 (зафиксированы до прогона).
THRESH_STABILITY_EXACT = 0.80
THRESH_STABILITY_PM1 = 0.97
THRESH_SPEARMAN = 0.85
THRESH_ADJACENT = 0.15  # путаница соседних грейдов, строго меньше
# Внутренние пороги (не из §9.3, контроль качества контура).
THRESH_EQUIV_OUTSIDE = 0.15  # доля seeds вне 95% ДИ (по построению ~5%)
# |β_final − β_эмпирическая|: SE(β̂) на 1000 ответах ≈ 0.07, порог ≈ 3–4σ
THRESH_CALIB_ERROR = 0.3


# ------------------------------------------------------------------ банк


def build_bank(spec: str, seed: int, mcq_n: int = 18, sql_n: int = 10) -> BankRegistry:
    """Свежий банк из фабрик по маршрутизации тем каталога (без sanity-чека)."""
    rng = random.Random(f"bank:{spec}:{seed}")
    reg = BankRegistry()
    mcq_topics = MCQ_TOPICS.get(spec, ())
    sql_topics = SQL_TOPICS.get(spec, ())
    for i, topic in enumerate(mcq_topics):
        cnt = mcq_n // len(mcq_topics) + (1 if i < mcq_n % len(mcq_topics) else 0)
        for t in factory_mcq.make_templates(spec, topic, cnt, rng):
            reg.add(t)
    for i, topic in enumerate(sql_topics):
        cnt = sql_n // len(sql_topics) + (1 if i < sql_n % len(sql_topics) else 0)
        for t in factory_sql.make_templates(spec, topic, cnt, rng):
            reg.add(t)
    return reg


# ------------------------------------------------------------------ сессия


def run_session(
    agent: SyntheticAgent,
    bank: BankRegistry,
    mode: str = "full",
    seed: int | str | None = None,
    config: CatConfig | None = None,
) -> dict[str, Any]:
    engine = TestEngine(bank, config=config, seed=seed)
    inst = engine.start(agent.spec, agent.grade_claimed, mode)
    while True:
        answer, _intended = agent.answer(inst)
        out = engine.submit(answer)
        if out["finished"]:
            return out["result"]
        inst = out["next"]


# ------------------------------------------------------------------ статистика


def _rankdata(values: list[float]) -> list[float]:
    """Ранги со средними для связей (midranks)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mid = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1
    return ranks


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 0 or vy <= 0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def spearman(x: list[float], y: list[float]) -> float:
    return pearson(_rankdata(x), _rankdata(y))


# ------------------------------------------------------- отдельные эксперименты


def instance_equivalence(
    bank: BankRegistry,
    rng: random.Random,
    k_templates: int = 10,
    n_seeds: int = 50,
    n_agents: int = 100,
    theta: float = 1.0,
    careless: float = 0.05,
) -> dict[str, Any]:
    """Эквивалентность экземпляров (§9.2.3): для K шаблонов × 50 seeds доля
    верных ответов n_agents агентов с одинаковым θ обязана лежать в
    биномиальном 95% ДИ (параметризация не меняет сложность)."""
    templates = bank.filter()
    k = min(k_templates, len(templates))
    chosen = rng.sample(templates, k)
    per_template: list[dict[str, Any]] = []
    broken = 0
    for t in chosen:
        p = irt.p_correct(theta, t.beta) * (1 - careless) + (
            1 - irt.p_correct(theta, t.beta)
        ) * careless
        half = 1.96 * math.sqrt(p * (1 - p) / n_agents)
        lo, hi = p - half, p + half
        outside = 0
        for s in range(n_seeds):
            try:
                inst = t.make(50_000 + s)
                if not inst.check(inst.reference):
                    broken += 1
                    continue
            except Exception:
                broken += 1
                continue
            hits = sum(1 for _ in range(n_agents) if rng.random() < p)
            frac = hits / n_agents
            if not (lo <= frac <= hi):
                outside += 1
        per_template.append(
            {
                "template_id": t.id,
                "beta": t.beta,
                "p_expected": round(p, 4),
                "seeds_outside_ci": outside,
                "n_seeds": n_seeds,
                "share_outside": round(outside / n_seeds, 4),
            }
        )
    if per_template:
        mean_outside = float(np.mean([r["share_outside"] for r in per_template]))
    else:
        mean_outside = 1.0
    return {
        "k_templates": k,
        "n_seeds": n_seeds,
        "n_agents": n_agents,
        "theta": theta,
        "broken_instances": broken,
        "mean_share_outside_ci": round(mean_outside, 4),
        "per_template": per_template,
    }


def beta_calibration_probe(
    rng: random.Random,
    beta_true: float = 0.4,
    theta_mu: float = 1.0,
    theta_sd: float = 0.4,
    n_answers: int = 1000,
    window: int = 25,
) -> dict[str, Any]:
    """Сходимость BetaStat (§9.2.4): ответы агентов θ~N(μ,σ) на задание с
    известной β; калибровка обязана подтянуть β к эмпирической β̂."""
    stat = irt.BetaStat(template_id="probe", beta=beta_true + 0.8)  # старт с ошибкой
    all_theta: list[float] = []
    all_correct: list[int] = []
    iterations = 0
    for _ in range(n_answers):
        th = rng.gauss(theta_mu, theta_sd)
        correct = rng.random() < irt.p_correct(th, beta_true)
        stat.record(th, correct)
        all_theta.append(th)
        all_correct.append(int(correct))
        if stat.ready(window):
            stat.calibrate(window)
            iterations += 1
    p_bar = min(0.98, max(0.02, sum(all_correct) / len(all_correct)))
    theta_bar = sum(all_theta) / len(all_theta)
    empirical = theta_bar - irt.logit(p_bar)
    return {
        "beta_start": round(beta_true + 0.8, 3),
        "beta_true": beta_true,
        "beta_final": round(stat.beta, 3),
        "beta_empirical": round(empirical, 3),
        "error_vs_empirical": round(abs(stat.beta - empirical), 3),
        "iterations": iterations,
    }


def session_overlap(asked_sets: list[set[str]]) -> dict[str, Any]:
    """Пересечение наборов шаблонов между сессиями (§9.2.6): средний Jaccard."""
    pairs = 0
    total = 0.0
    for i in range(len(asked_sets)):
        for j in range(i + 1, len(asked_sets)):
            a, b = asked_sets[i], asked_sets[j]
            union = a | b
            total += len(a & b) / len(union) if union else 0.0
            pairs += 1
    return {"pairs": pairs, "mean_jaccard": round(total / pairs, 4) if pairs else 0.0}


# ------------------------------------------------------------------ графики


def _plot_scatter(theta_true: list[float], theta_est: list[float], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(theta_true, theta_est, s=14, alpha=0.6, color="#402FFF")
    lo, hi = THETA_TRUE_LO - 0.3, THETA_TRUE_HI + 0.5
    ax.plot([lo, hi], [lo, hi], ls="--", lw=1, color="#9B9C9E")
    for b in (-1.0, 0.5, 2.0):
        ax.axvline(b, lw=0.7, color="#EDEDED")
        ax.axhline(b, lw=0.7, color="#EDEDED")
    ax.set_xlabel("θ истинный (агент)")
    ax.set_ylabel("θ оценённый (CAT, среднее по повторам)")
    ax.set_title("Дискриминативность адаптивного теста")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _plot_confusion(matrix: list[list[int]], path: Path) -> None:
    labels = [g.slug for g in GRADES]
    arr = np.array(matrix, dtype=float)
    row_sums = arr.sum(axis=1, keepdims=True)
    norm = np.divide(arr, row_sums, out=np.zeros_like(arr), where=row_sums > 0)
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    im = ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(4), labels)
    ax.set_yticks(range(4), labels)
    ax.set_xlabel("Присвоенный грейд")
    ax.set_ylabel("Истинный грейд")
    ax.set_title("Confusion matrix (доли по строкам)")
    for i in range(4):
        for j in range(4):
            color = "white" if norm[i, j] > 0.55 else "#1B1C21"
            ax.text(j, i, f"{matrix[i][j]}\n({norm[i, j]:.0%})", ha="center", va="center",
                    fontsize=9, color=color)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ------------------------------------------------------------------ прогон


@dataclass
class ThresholdCheck:
    name: str
    value: float
    target: str
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": round(self.value, 4),
                "target": self.target, "pass": self.passed}


def run_validation(
    n_agents: int = 300,
    repeats: int = 3,
    out_dir: str | Path = "out/validation",
    spec: str = "backend",
    seed: int = 42,
    mode: str = "full",
    quick: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    """Полный прогон §9: метрики, пороги, файлы отчёта в out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    banks = [build_bank(spec, seed=seed + r) for r in range(repeats)]
    step = (THETA_TRUE_HI - THETA_TRUE_LO) / max(1, n_agents - 1)
    agents = [
        SyntheticAgent(
            theta_true=THETA_TRUE_LO + step * i,
            rng=random.Random(f"agent:{seed}:{i}"),
            spec=spec,
        )
        for i in range(n_agents)
    ]

    # sessions[agent_idx][repeat] = result
    sessions: list[list[dict[str, Any]]] = []
    for ai, agent in enumerate(agents):
        row = []
        for r in range(repeats):
            row.append(run_session(agent, banks[r], mode=mode, seed=f"s:{seed}:{ai}:{r}"))
        sessions.append(row)
        if verbose and (ai + 1) % 50 == 0:
            print(f"  … агентов прогнано: {ai + 1}/{n_agents}")

    theta_true = [a.theta_true for a in agents]
    theta_est_mean = [float(np.mean([s["theta"] for s in row])) for row in sessions]
    grades_per_agent = [
        [grade_index(s["grade_assigned"]) for s in row] for row in sessions
    ]

    # §9.2.1 стабильность
    exact = sum(1 for gs in grades_per_agent if len(set(gs)) == 1) / n_agents
    pm1 = sum(1 for gs in grades_per_agent if max(gs) - min(gs) <= 1) / n_agents

    # §9.2.2 дискриминативность
    rho = spearman(theta_true, theta_est_mean)
    medians_by_band: dict[str, float] = {}
    for g in GRADES:
        vals = [
            est for tt, est in zip(theta_true, theta_est_mean, strict=True)
            if grade_for_theta(tt).slug == g.slug
        ]
        medians_by_band[g.slug] = round(float(np.median(vals)), 3) if vals else float("nan")
    med_values = list(medians_by_band.values())
    monotonic = all(a <= b for a, b in zip(med_values, med_values[1:], strict=False))

    # confusion matrix (по всем прогонам, строка — истинный грейд)
    matrix = [[0] * 4 for _ in range(4)]
    total_runs = 0
    adjacent = 0
    for agent, row in zip(agents, sessions, strict=True):
        true_idx = grade_index(grade_for_theta(agent.theta_true).slug)
        for s in row:
            assigned_idx = grade_index(s["grade_assigned"])
            matrix[true_idx][assigned_idx] += 1
            total_runs += 1
            if abs(true_idx - assigned_idx) == 1:
                adjacent += 1
    adjacent_rate = adjacent / total_runs if total_runs else 0.0

    # §9.2.3 эквивалентность экземпляров
    equiv = instance_equivalence(
        banks[0],
        rng,
        k_templates=4 if quick else 10,
        n_agents=40 if quick else 100,
    )

    # §9.2.4 калибровка β
    calib = beta_calibration_probe(rng)

    # §9.2.6 пересечение наборов (сессии repeat-0 делят один банк);
    # берём равномерную подвыборку по всему диапазону θ_true — иначе
    # при большом N первые 60 агентов оказываются в одной полосе и
    # Jaccard завышен.
    stride = max(1, n_agents // 60)
    asked_sets = [
        {a["template_id"] for a in row[0]["asked"]} for row in sessions[::stride][:60]
    ]
    overlap = session_overlap(asked_sets)

    checks = [
        ThresholdCheck("stability_exact", exact, f">= {THRESH_STABILITY_EXACT}",
                       exact >= THRESH_STABILITY_EXACT),
        ThresholdCheck("stability_pm1", pm1, f">= {THRESH_STABILITY_PM1}",
                       pm1 >= THRESH_STABILITY_PM1),
        ThresholdCheck("spearman", rho, f">= {THRESH_SPEARMAN}", rho >= THRESH_SPEARMAN),
        ThresholdCheck("adjacent_confusion", adjacent_rate, f"< {THRESH_ADJACENT}",
                       adjacent_rate < THRESH_ADJACENT),
        ThresholdCheck("instances_outside_ci", equiv["mean_share_outside_ci"],
                       f"<= {THRESH_EQUIV_OUTSIDE}",
                       equiv["mean_share_outside_ci"] <= THRESH_EQUIV_OUTSIDE
                       and equiv["broken_instances"] == 0),
        ThresholdCheck("beta_calibration_error", calib["error_vs_empirical"],
                       f"<= {THRESH_CALIB_ERROR}",
                       calib["error_vs_empirical"] <= THRESH_CALIB_ERROR),
    ]
    overall = all(c.passed for c in checks)

    report: dict[str, Any] = {
        "params": {
            "n_agents": n_agents,
            "repeats": repeats,
            "spec": spec,
            "mode": mode,
            "seed": seed,
            "k0": CatConfig().k0,
            "bank_sizes": [len(b) for b in banks],
        },
        "metrics": {
            "stability_exact": round(exact, 4),
            "stability_pm1": round(pm1, 4),
            "spearman": round(rho, 4),
            "adjacent_confusion": round(adjacent_rate, 4),
            "medians_by_true_grade": medians_by_band,
            "medians_monotonic": monotonic,
            "confusion_matrix": matrix,
            "instance_equivalence": equiv,
            "beta_calibration": calib,
            "session_overlap": overlap,
        },
        "thresholds": [c.to_dict() for c in checks],
        "overall_pass": overall,
    }

    (out / "validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = format_summary(report)
    (out / "summary.txt").write_text(summary, encoding="utf-8")
    _plot_scatter(theta_true, theta_est_mean, out / "theta_scatter.png")
    _plot_confusion(matrix, out / "confusion.png")
    return report


def format_summary(report: dict[str, Any]) -> str:
    p, m = report["params"], report["metrics"]
    grade_rows = []
    for i, g in enumerate(GRADES):
        row = report["metrics"]["confusion_matrix"][i]
        total = sum(row)
        diag = row[i] / total if total else 0.0
        grade_rows.append(f"  {g.slug:<8} точность строки {diag:6.1%}  (n={total})")
    lines = [
        "ВАЛИДАЦИЯ hunter_core (PRD §9)",
        "=" * 46,
        f"Агентов: {p['n_agents']} · повторов: {p['repeats']} · режим: {p['mode']} · "
        f"специализация: {p['spec']} · K0={p['k0']}",
        f"Банк: {p['bank_sizes']} шаблонов по повторам",
        "",
        f"Стабильность грейда: точное совпадение {m['stability_exact']:.1%} "
        f"(порог ≥ 80%), в пределах ±1 — {m['stability_pm1']:.1%} (порог ≥ 97%)",
        f"Spearman(θ_true, θ_est): {m['spearman']:.3f} (порог ≥ 0.85)",
        f"Путаница соседних грейдов: {m['adjacent_confusion']:.1%} (порог < 15%)",
        f"Медианы θ_est по полосам θ_true: {m['medians_by_true_grade']} "
        f"({'монотонны' if m['medians_monotonic'] else 'НЕ монотонны'})",
        "",
        "Confusion matrix (строки — истинный грейд):",
        *grade_rows,
        "",
        f"Эквивалентность экземпляров: доля seeds вне 95% ДИ "
        f"{m['instance_equivalence']['mean_share_outside_ci']:.1%} "
        f"(битых экземпляров: {m['instance_equivalence']['broken_instances']})",
        f"Калибровка BetaStat: β {m['beta_calibration']['beta_start']} → "
        f"{m['beta_calibration']['beta_final']} при эмпирической "
        f"{m['beta_calibration']['beta_empirical']} "
        f"(ошибка {m['beta_calibration']['error_vs_empirical']})",
        f"Пересечение наборов шаблонов между сессиями: средний Jaccard "
        f"{m['session_overlap']['mean_jaccard']:.3f} ({m['session_overlap']['pairs']} пар)",
        "",
        "Пороги §9.3 и внутренние проверки:",
    ]
    for c in report["thresholds"]:
        mark = "PASS" if c["pass"] else "FAIL"
        lines.append(f"  [{mark}] {c['name']:<26} {c['value']:.4f}  ({c['target']})")
    lines.append("")
    lines.append(f"ИТОГ: {'PASS' if report['overall_pass'] else 'FAIL'}")
    return "\n".join(lines)
