"""CAT-движок: исходы по уровням агентов, длины режимов, устойчивость."""

import random

import pytest

from engine import cat as cat_module
from validation.agents import SyntheticAgent
from validation.harness import build_bank, run_session

CatConfig = cat_module.CatConfig


@pytest.fixture(scope="module")
def bank():
    return build_bank("backend", seed=202, mcq_n=18, sql_n=10)


def _run(theta_true: float, grade: str, bank, seed: int, mode: str = "full"):
    agent = SyntheticAgent(theta_true=theta_true, rng=random.Random(f"agent:{seed}"))
    engine = cat_module.TestEngine(bank, seed=f"eng:{seed}")
    inst = engine.start("backend", grade, mode)
    while True:
        answer, _ = agent.answer(inst)
        out = engine.submit(answer)
        if out["finished"]:
            return out["result"]
        inst = out["next"]


def test_strong_agent_gets_senior_or_upgrade(bank):
    """Агент θ=2.5, заявивший middle: сеньор по оценке или upgrade_offer (≥5/8)."""
    hits = 0
    for seed in range(8):
        result = _run(2.5, "middle", bank, seed)
        assert result["grade_assigned"] in ("middle", "senior"), result
        if result["grade_assigned"] == "senior" or result["outcome"] == "upgrade_offer":
            hits += 1
    assert hits >= 5


def test_strong_agent_claiming_senior_confirmed(bank):
    for seed in range(8):
        result = _run(2.5, "senior", bank, seed)
        assert result["outcome"] == "confirmed", result
        assert result["grade_verified"] == "senior"
        assert result["grade_assigned"] == "senior"


def test_weak_agent_gets_intern_or_downgrade(bank):
    """Агент θ=−2, заявивший junior: intern по оценке или downgrade_offer (≥5/8)."""
    hits = 0
    for seed in range(8):
        result = _run(-2.0, "junior", bank, seed)
        if result["grade_assigned"] == "intern" or result["outcome"] == "downgrade_offer":
            hits += 1
    assert hits >= 5


def test_weak_agent_claiming_intern_confirmed(bank):
    for seed in range(8):
        result = _run(-2.0, "intern", bank, seed)
        assert result["outcome"] == "confirmed", result
        assert result["grade_assigned"] == "intern"


def test_downgrade_offer_never_forces_grade(bank):
    for seed in range(8):
        result = _run(-2.0, "middle", bank, seed)
        if result["outcome"] == "downgrade_offer":
            assert result["grade_verified"] is None


def test_express_mode_stops_at_four(bank):
    result = _run(1.0, "middle", bank, seed=11, mode="express")
    assert len(result["asked"]) == 4
    assert result["mode"] == "express"


def test_full_mode_stops_at_ten(bank):
    result = _run(1.0, "middle", bank, seed=12)
    assert len(result["asked"]) == 10


def test_result_structure(bank):
    result = _run(1.0, "middle", bank, seed=13)
    for key in ("theta", "se", "outcome", "grade_verified", "grade_assigned",
                "asked", "breakdown", "p_upgrade", "p_downgrade"):
        assert key in result
    for a in result["asked"]:
        assert {"template_id", "seed", "correct"} <= set(a)
    assert sum(b["asked"] for b in result["breakdown"].values()) == len(result["asked"])


def test_no_template_reuse_within_session(bank):
    result = _run(1.0, "middle", bank, seed=14)
    ids = [a["template_id"] for a in result["asked"]]
    assert len(ids) == len(set(ids))


def test_topics_round_robin(bank):
    result = _run(1.0, "middle", bank, seed=15)
    topics = [a["topic"] for a in result["asked"]]
    # за 10 вопросов каждая из 5 тем задана хотя бы раз
    assert len(set(topics)) == 5


def test_tiny_bank_finishes_early():
    bank = build_bank("backend", seed=777, mcq_n=2, sql_n=0)
    agent = SyntheticAgent(theta_true=1.0, rng=random.Random(1))
    result = run_session(agent, bank, seed=1)
    assert 1 <= len(result["asked"]) <= 2


def test_k0_config_override(bank):
    cfg = CatConfig(k0=0.9)
    agent = SyntheticAgent(theta_true=1.0, rng=random.Random(2))
    result = run_session(agent, bank, seed=2, config=cfg)
    assert result["asked"][0]["theta_after"] != 0.0
