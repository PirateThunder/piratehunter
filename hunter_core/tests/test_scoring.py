"""Скоринг: test_score/fsp_score/freshness/stack_match/match_score (§7.5.2, §7.9)."""

from datetime import UTC, datetime, timedelta

from engine import scoring
from engine.scoring import (
    DEFAULT_WEIGHTS,
    freshness,
    fsp_score,
    match_score,
    stack_match,
)

NOW = datetime(2026, 10, 7, tzinfo=UTC)


def test_fsp_anti_gaming():
    """10 участий < 1 победы (защита от набивания явками, §7.9)."""
    ten_participations = fsp_score(contests=["participant"] * 10)
    one_win = fsp_score(contests=["winner"])
    assert ten_participations < one_win
    assert ten_participations == fsp_score(contests=["participant"] * 10)
    assert 0.29 < ten_participations < 0.31  # 0.15·(2 − 2^-9)


def test_fsp_weights_and_cap():
    assert fsp_score(contests=["diploma"]) == 0.7
    assert fsp_score(contests=["prize"]) == 0.5
    assert fsp_score(events=[{}, {}, {}]) < 0.15  # мероприятия тоже затухают
    assert fsp_score(contests=["winner", "winner", "winner"]) == 1.0  # cap
    assert fsp_score() == 0.0  # нет истории → 0, штрафа нет
    assert fsp_score(contests=[{"result": "winner"}]) == 1.0  # dict-форма


def test_test_score_band_position():
    assert scoring.test_score(1.25, "middle") == 0.5  # медиана полосы middle
    assert scoring.test_score(0.5, "middle") == 0.0
    assert scoring.test_score(2.0, "middle") == 1.0  # clamp сверху
    assert scoring.test_score(-2.5, "intern") == 0.5


def test_test_score_unverified_cap():
    assert scoring.test_score(3.9, "senior", verified=False) == 0.4
    assert scoring.test_score(2.05, "senior", verified=False) <= 0.4
    assert scoring.test_score(3.9, "senior", verified=True) > 0.9


def test_freshness_half_life():
    assert freshness((NOW - timedelta(days=30)).isoformat(), NOW) == 0.5
    assert freshness(NOW.isoformat(), NOW) == 1.0
    assert freshness((NOW - timedelta(days=60)).isoformat(), NOW) == 0.25
    assert freshness(None, NOW) == 0.0


def test_stack_match_must_weighs_triple():
    cand = ["python", "fastapi"]
    must_hit = stack_match(cand, must=["python"], nice=["fastapi"])
    # 3·1 + 1 = 4 из 3·1 + 1 = 4 → 1.0
    assert must_hit == 1.0
    only_nice = stack_match(cand, must=["java"], nice=["python", "fastapi"])
    # 0 + 2 из 3·1 + 2 = 5 → 0.4
    assert abs(only_nice - 0.4) < 1e-9
    only_must = stack_match(["python"], must=["python"], nice=["fastapi", "redis"])
    # 3 из 3 + 2 = 5 → 0.6: must весит больше двух nice
    assert abs(only_must - 0.6) < 1e-9
    assert stack_match([], [], []) == 0.0
    assert stack_match(["Python"], ["python"], []) == 1.0  # регистр не важен


def test_match_score_explanation_full():
    snapshot = {
        "theta": 1.25,
        "grade": "middle",
        "verified": True,
        "stack": ["python", "postgresql", "docker", "fastapi"],
        "fsp_score": 0.7,
        "last_active_at": (NOW - timedelta(days=5)).isoformat(),
    }
    need = {"stack_must": ["python", "postgresql"], "stack_nice": ["docker"]}
    score, explanation = match_score(snapshot, need, now=NOW)
    assert {e["factor"] for e in explanation} == {"test", "stack", "fsp", "freshness"}
    assert len(explanation) == 4
    for e in explanation:
        assert e["weight"] == DEFAULT_WEIGHTS[e["factor"]]
        assert abs(e["contribution"] - e["weight"] * e["value"]) < 1e-3
        assert e["human_text"]
    assert abs(score - sum(e["contribution"] for e in explanation)) < 1e-3
    # сильный кандидат под свой запрос — высокий score
    assert score > 0.7


def test_match_score_unverified_lowers_score():
    base = {
        "theta": 1.9,
        "grade": "middle",
        "stack": ["python"],
        "fsp_score": 0.0,
        "last_active_at": NOW.isoformat(),
    }
    need = {"stack_must": ["python"], "stack_nice": []}
    verified_score, _ = match_score({**base, "verified": True}, need, now=NOW)
    unverified_score, expl = match_score({**base, "verified": False}, need, now=NOW)
    assert unverified_score < verified_score
    test_factor = next(e for e in expl if e["factor"] == "test")
    assert test_factor["value"] <= 0.4
    assert "не подтверждён" in test_factor["human_text"]


def test_match_score_custom_weights():
    snapshot = {"theta": 1.25, "grade": "middle", "verified": True,
                "stack": ["python"], "fsp_score": 0.0, "last_active_at": NOW.isoformat()}
    need = {"stack_must": ["python"], "stack_nice": []}
    score, explanation = match_score(snapshot, need, weights={"test": 0.0, "stack": 1.0,
                                                              "fsp": 0.0, "freshness": 0.0},
                                     now=NOW)
    assert score == 1.0  # только стек, полное совпадение must
