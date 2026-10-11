from datetime import date

from app.profiles.constants import DISCIPLINES, EVENT_ROLES
from app.profiles.service import build_profile

# первый fsp_id из пробы с историей / без — находим детерминированно,
# чтобы тесты не зависели от конкретной соли генератора
WITH_HISTORY = next(f"probe-{i}" for i in range(100) if build_profile(f"probe-{i}"))
WITHOUT_HISTORY = next(f"probe-{i}" for i in range(100) if not build_profile(f"probe-{i}"))


async def test_profile_deterministic(client):
    first = await client.get(f"/fsp/v1/profiles/{WITH_HISTORY}")
    second = await client.get(f"/fsp/v1/profiles/{WITH_HISTORY}")
    assert first.status_code == 200
    assert first.json() == second.json()


async def test_profile_404_deterministic(client):
    first = await client.get(f"/fsp/v1/profiles/{WITHOUT_HISTORY}")
    second = await client.get(f"/fsp/v1/profiles/{WITHOUT_HISTORY}")
    assert first.status_code == 404
    assert second.status_code == 404
    assert "detail" in first.json()


def test_404_share_on_large_sample():
    n = 3000
    missing = sum(1 for i in range(n) if build_profile(f"share-{i}") is None)
    share = missing / n
    assert 0.35 <= share <= 0.45, f"доля 404 = {share:.3f}, ожидаем ~0.40"


async def test_profile_schema_invariants(client):
    checked = 0
    for i in range(100):
        resp = await client.get(f"/fsp/v1/profiles/schema-{i}")
        if resp.status_code == 404:
            continue
        body = resp.json()
        assert body["fsp_id"] == f"schema-{i}"
        assert isinstance(body["rating"], int) and body["rating"] > 0

        assert body["contests"], "профиль с историей должен иметь контесты"
        for contest in body["contests"]:
            assert contest["discipline"] in DISCIPLINES
            assert contest["place"] >= 1
            assert date.fromisoformat(contest["date"]) < date(2026, 10, 1)
            assert contest["diploma"] in (1, 2, 3, None)
            if contest["diploma"] is not None:
                assert contest["place"] == contest["diploma"]
            assert (contest["team_result"] is not None) == contest["team"]
            if contest["team_result"]:
                assert contest["team_result"]["team_name"]
                assert contest["team_result"]["place"] >= 1

        for rank in body["ranks"]:
            assert rank["discipline"] in DISCIPLINES
            assert rank["rank"]
            assert date.fromisoformat(rank["date"]) < date(2026, 10, 1)

        for event in body["events"]:
            assert event["role"] in EVENT_ROLES
            assert date.fromisoformat(event["date"]) < date(2026, 10, 1)

        checked += 1
    assert checked >= 40, f"проверено только {checked} профилей из 100 — похоже на сбой генератора"


def test_oidc_identities_have_mixed_history():
    # PRD §8.3: часть синтетических личностей с историей, часть — с 404
    from app.oidc.constants import IDENTITIES

    with_history = [i.fsp_id for i in IDENTITIES if build_profile(i.fsp_id)]
    assert 6 <= len(with_history) <= 18, (
        f"история есть у {len(with_history)}/20 личностей — ожидаем заметный микс"
    )
