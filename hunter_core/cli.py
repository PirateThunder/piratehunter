#!/usr/bin/env python3
"""Единый CLI hunter_core (запуск: uv run python cli.py <команда>).

Команды:
  catalog       — справочник специализаций и грейдов (PRD §6)
  bank-build    — сборка банка заданий фабриками + sanity-чек (PRD §10)
  test-sim      — симуляция тест-сессии синтетическим агентом (ход теста)
  validate      — полный валидационный прогон §9 с графиками и PASS/FAIL
  match-eval    — Precision@5 / nDCG@10 подбора на синтетике (§9.2.5)
  reword-demo   — демо LLM-перефразировки оболочки задания (OpenRouter)
"""

from __future__ import annotations

import argparse
import json
import random
import sys

from engine.cat import TestEngine
from engine.catalog import (
    GRADES,
    MCQ_TOPICS,
    SPECIALIZATIONS,
    SQL_TOPICS,
)


def _cmd_catalog(_args: argparse.Namespace) -> int:
    print("СПЕЦИАЛИЗАЦИИ (PRD §6)\n")
    for spec in SPECIALIZATIONS:
        topics = ", ".join(f"{t.slug} «{t.title}»" for t in spec.topics)
        print(f"{spec.slug:<10} {spec.title}")
        print(f"{'':<10} темы ({len(spec.topics)}): {topics}")
    print("\nГРЕЙДЫ (θ-полосы)\n")
    for g in GRADES:
        hi = f"{g.hi:g}" if g.slug != "senior" else "…"
        print(f"{g.slug:<8} {g.title:<10} [{g.lo:g}; {hi})  "
              f"медиана {g.median:g}  — {g.description}")
    return 0


def _build_bank(spec: str, mcq_n: int, sql_n: int, seed: int):
    from itembank import BankRegistry, factory_mcq, factory_sql

    rng = random.Random(f"bank-build:{spec}:{seed}")
    reg = BankRegistry()
    skipped: list[str] = []
    mcq_topics = MCQ_TOPICS.get(spec, ())
    sql_topics = SQL_TOPICS.get(spec, ())
    if not mcq_topics and mcq_n:
        skipped.append(f"mcq (нет кодовых тем для {spec})")
    if not sql_topics and sql_n:
        skipped.append(f"sql (нет SQL-тем для {spec})")
    for i, topic in enumerate(mcq_topics):
        cnt = mcq_n // len(mcq_topics) + (1 if i < mcq_n % len(mcq_topics) else 0)
        for t in factory_mcq.make_templates(spec, topic, cnt, rng):
            reg.add(t)
    for i, topic in enumerate(sql_topics):
        cnt = sql_n // len(sql_topics) + (1 if i < sql_n % len(sql_topics) else 0)
        for t in factory_sql.make_templates(spec, topic, cnt, rng):
            reg.add(t)
    return reg, skipped


def _cmd_bank_build(args: argparse.Namespace) -> int:
    from itembank import sanity_check_template

    reg, skipped = _build_bank(args.spec, args.mcq, args.sql, args.seed)
    for note in skipped:
        print(f"ВНИМАНИЕ: пропущены фабрики: {note}")
    print(f"Сгенерировано шаблонов: {len(reg)}; sanity-чек по {args.seeds} seeds…\n")
    kept, rejected = [], []
    for t in reg.filter(active_only=False):
        report = sanity_check_template(t, n_seeds=args.seeds)
        if report.ok:
            kept.append(t)
        else:
            rejected.append(report)
    out_reg = type(reg)(kept)
    out_reg.to_json(args.out)
    betas = sorted(t.beta for t in kept)
    print(f"Прошло sanity: {len(kept)}; отбраковано: {len(rejected)}")
    for rep in rejected:
        print(f"  ОТКАЗ {rep.template_id}: {rep.failures[0]}")
    if betas:
        print(f"β: min {betas[0]:.2f} · медиана {betas[len(betas) // 2]:.2f} · max {betas[-1]:.2f}")
    by_kind: dict[str, int] = {}
    by_band: dict[str, int] = {}
    for t in kept:
        by_kind[t.kind] = by_kind.get(t.kind, 0) + 1
        by_band[t.grade_band] = by_band.get(t.grade_band, 0) + 1
    print(f"По типам: {by_kind}; по полосам: {by_band}")
    print(f"Банк записан: {args.out}")
    return 0 if not rejected else 2


def _cmd_test_sim(args: argparse.Namespace) -> int:
    from validation.agents import SyntheticAgent

    reg, _skipped = _build_bank(args.spec, args.mcq, args.sql, args.seed)
    agent = SyntheticAgent(
        theta_true=args.theta_true, rng=random.Random(f"sim:{args.seed}"), spec=args.spec
    )
    mode = "express" if args.express else "full"
    engine = TestEngine(reg, seed=f"sim-engine:{args.seed}")
    inst = engine.start(args.spec, args.grade, mode)
    print(
        f"Симуляция: spec={args.spec}, заявленный грейд={args.grade}, "
        f"режим={mode}, θ_true={args.theta_true}\n"
    )
    step = 0
    while True:
        step += 1
        print(f"── Вопрос {step}/{engine.max_questions} · тема {inst.topic} · "
              f"β={inst.beta:.2f} · {inst.kind} · лимит {inst.time_limit_s}с")
        print(inst.question_text)
        if inst.kind == "mcq":
            for i, opt in enumerate(inst.payload["options"]):
                print(f"   {i + 1}) {opt}")
        answer, intended = agent.answer(inst)
        out = engine.submit(answer)
        mark = "верно" if out["correct"] else "НЕВЕРНО"
        shown = str(answer) if len(str(answer)) < 60 else str(answer)[:57] + "…"
        print(f"→ ответ агента ({'целился верно' if intended else 'ошибка'}): {shown}")
        print(f"  чекер: {mark}; θ={engine.theta:.3f}, SE={engine.se:.3f}\n")
        if out["finished"]:
            result = out["result"]
            break
        inst = out["next"]
    print("═" * 60)
    print("РЕЗУЛЬТАТ:")
    result_view = {k: v for k, v in result.items() if k != "asked"}
    print(json.dumps(result_view, ensure_ascii=False, indent=2))
    print("\nЗаданные вопросы:")
    for a in result["asked"]:
        print(f"  {a['template_id']:<22} seed={a['seed']:<12} β={a['beta']:.2f} "
              f"{'✓' if a['correct'] else '✗'} θ→{a['theta_after']:.2f}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from validation.harness import format_summary, run_validation

    report = run_validation(
        n_agents=args.agents,
        repeats=args.repeats,
        out_dir=args.out,
        spec=args.spec,
        seed=args.seed,
        quick=args.quick,
    )
    print()
    print(format_summary(report))
    print(f"\nФайлы: {args.out}/validation.json, summary.txt, theta_scatter.png, confusion.png")
    return 0 if report["overall_pass"] else 1


def _cmd_match_eval(args: argparse.Namespace) -> int:
    from validation.matching_eval import run_matching_eval

    report = run_matching_eval(out_path=args.out, seed=args.seed)
    m = report["metrics"]
    print("ПОДБОР (PRD §9.2.5): 50 кандидатов × 20 потребностей, синтетика")
    print(f"Precision@5 = {m['precision_at_5']:.3f} (порог ≥ 0.8)")
    print(f"nDCG@10     = {m['ndcg_at_10']:.3f}")
    print(f"ИТОГ: {'PASS' if report['overall_pass'] else 'FAIL'}")
    if args.out:
        print(f"Отчёт: {args.out}")
    return 0 if report["overall_pass"] else 1


def _cmd_reword_demo(args: argparse.Namespace) -> int:
    from llm.client import LLMClient, reword_shell

    client = LLMClient.from_env()
    print("ИСХОДНЫЙ ТЕКСТ:")
    print(args.text)
    print()
    if not client.available:
        print("OPENROUTER_API_KEY не задан — перефразировка недоступна, "
              "возвращён исходный текст (fallback, PRD §3.4).")
        print("\nРЕЗУЛЬТАТ (fallback):")
        print(args.text)
        return 0
    print(f"Модель: {client.model}; перефразирую…\n")
    out = reword_shell(args.text, args.topic, client)
    print("РЕЗУЛЬТАТ:")
    print(out)
    if out == args.text:
        print("\n(ответ модели отклонён страховкой или LLM недоступна — fallback)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hunter-core",
        description="CLI-ядро платформы подбора ИТ-специалистов: банк заданий, "
        "CAT-тест, скоринг, валидация",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("catalog", help="печать справочника §6")
    p.set_defaults(fn=_cmd_catalog)

    p = sub.add_parser("bank-build", help="сборка банка заданий + sanity-чек")
    p.add_argument("--spec", default="backend")
    p.add_argument("--mcq", type=int, default=15, help="mcq-шаблонов (по темам маппинга)")
    p.add_argument("--sql", type=int, default=8, help="sql-шаблонов")
    p.add_argument("--out", default=None, help="куда писать JSON (default out/bank_<spec>.json)")
    p.add_argument("--seeds", type=int, default=20, help="seeds на шаблон в sanity-чеке")
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(fn=_cmd_bank_build)

    p = sub.add_parser("test-sim", help="симуляция тест-сессии агентом")
    p.add_argument("--spec", default="backend")
    p.add_argument("--grade", default="middle")
    p.add_argument("--theta-true", type=float, default=1.0)
    p.add_argument("--express", action="store_true")
    p.add_argument("--mcq", type=int, default=18)
    p.add_argument("--sql", type=int, default=10)
    p.add_argument("--seed", type=int, default=7)
    p.set_defaults(fn=_cmd_test_sim)

    p = sub.add_parser("validate", help="полный валидационный прогон §9")
    p.add_argument("--agents", type=int, default=300)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--spec", default="backend")
    p.add_argument("--out", default="out/validation")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--quick", action="store_true", help="урезанные эксперименты (быстрее)")
    p.set_defaults(fn=_cmd_validate)

    p = sub.add_parser("match-eval", help="Precision@5 / nDCG@10 подбора")
    p.add_argument("--out", default="out/validation/matching.json")
    p.add_argument("--seed", type=int, default=11)
    p.set_defaults(fn=_cmd_match_eval)

    p = sub.add_parser("reword-demo", help="демо LLM-перефразировки оболочки задания")
    p.add_argument("text", help="текст задания")
    p.add_argument("--topic", default="python")
    p.set_defaults(fn=_cmd_reword_demo)

    args = parser.parse_args(argv)
    if args.cmd == "bank-build" and args.out is None:
        args.out = f"out/bank_{args.spec}.json"
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
