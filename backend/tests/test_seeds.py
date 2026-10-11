"""Сиды (§10): детерминизм датасета, квоты, θ-полосы, предохранитель
env раннера. Живой реестр/БД здесь не дёргаем — pool подаётся
фикстурный."""

import pytest

from app.seeds import runner
from app.seeds.data import GRADE_BANDS
from app.seeds.dataset import (
    CANDIDATES_TOTAL,
    DEMO_CANDIDATE_EMAIL,
    DEMO_CANDIDATE_FSP_EMAIL,
    DEMO_EMPLOYER_EMAIL,
    FSP_SHARE,
    generate,
)


@pytest.fixture
def fsp_pool() -> dict[str, dict]:
    needed = round(CANDIDATES_TOTAL * FSP_SHARE)
    pool = {
        f"fsp-seed-{i:04d}": {
            "fsp_id": f"fsp-seed-{i:04d}",
            "rating": 1000 + i,
            "contests": [{"name": "Хакатон", "place": 2, "diploma": 2}],
            "events": [],
        }
        for i in range(1, needed + 1)
    }
    pool["fsp_001"] = {
        "fsp_id": "fsp_001", "rating": 2000,
        "contests": [{"name": "Чемпионат", "place": 1, "diploma": 1}],
        "events": [],
    }
    return pool


def test_dataset_digest_stable(fsp_pool):
    """Повторная генерация на том же входе — байт-в-байт тот же
    датасет (uuid5 + фиксированный rng)."""
    first = generate(dict(fsp_pool))
    second = generate(dict(fsp_pool))
    assert first.digest() == second.digest()


def test_dataset_quotas(fsp_pool):
    ds = generate(fsp_pool)
    assert len(ds.profiles) == CANDIDATES_TOTAL + 2  # + 2 демо-кандидата
    assert len(ds.companies) == 16  # 15 + Демо Корп
    assert len(ds.needs) >= 6
    assert 35 <= len(ds.invitations) <= 45
    # ~60% с историей ФСП (профили сид-кандидатов + demo-fsp)
    with_fsp = sum(1 for p in ds.profiles if p["fsp_data"] is not None)
    assert with_fsp == round(CANDIDATES_TOTAL * FSP_SHARE) + 1
    # ~75% verified среди сид-кандидатов
    verified = sum(
        1 for g in ds.grade_states
        if g["grade_verified"] is not None
        and g["candidate_id"] not in _demo_ids(ds)
    )
    assert verified == 228  # 216 матрица + 12 контрастных слотов


def _demo_ids(ds) -> set[str]:
    demo_emails = {DEMO_CANDIDATE_EMAIL, DEMO_CANDIDATE_FSP_EMAIL}
    return {u["id"] for u in ds.users if u["email"] in demo_emails}


def test_dataset_theta_strictly_in_band(fsp_pool):
    ds = generate(fsp_pool)
    for state in ds.grade_states:
        if state["grade_verified"] and state["theta"] is not None:
            lo, hi = GRADE_BANDS[state["grade_verified"]]
            assert lo < state["theta"] < hi, (
                f"θ={state['theta']} вне полосы {state['grade_verified']}"
            )


def test_dataset_demo_accounts(fsp_pool):
    ds = generate(fsp_pool)
    by_email = {u["email"]: u for u in ds.users}
    demo = by_email[DEMO_CANDIDATE_EMAIL]
    assert demo["role"] == "candidate" and demo["fsp_id"] is None
    demo_fsp = by_email[DEMO_CANDIDATE_FSP_EMAIL]
    assert demo_fsp["fsp_id"] == "fsp_001"
    employer = by_email[DEMO_EMPLOYER_EMAIL]
    assert employer["role"] == "employer"
    demo_company = next(
        c for c in ds.companies if c["user_id"] == employer["id"]
    )
    assert demo_company["name"] == "Демо Корп"
    # у демо-работодателя ≥ 3 потребностей (§10)
    demo_needs = [n for n in ds.needs if n["company_id"] == employer["id"]]
    assert len(demo_needs) >= 3
    # pending-приглашения демо-кандидату с ФСП (хук §7.11.3)
    pending = [
        i for i in ds.invitations
        if i["candidate_id"] == demo_fsp["id"] and i["status"] == "sent"
    ]
    assert 1 <= len(pending) <= 2
    assert all(i["salary_from"] >= 300_000 for i in pending)


def test_dataset_ids_deterministic_uuid5(fsp_pool):
    ds = generate(fsp_pool)
    other = generate(dict(fsp_pool))
    assert [u["id"] for u in ds.users] == [u["id"] for u in other.users]


def test_runner_guard_non_local_env(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "env", "prod")
    with pytest.raises(SystemExit, match="BACK_ENV=local"):
        import asyncio

        asyncio.run(runner.main())
