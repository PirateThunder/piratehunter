"""ФСП-интеграция §7.9: привязка/отвязка, fsp_score, обязательный
кейс «нет истории» (404 реестра → score 0, блок не показывается)."""

from app.fsp.scoring import compute_fsp_score
from tests.conftest import make_candidate

RICH_PROFILE = {
    "fsp_id": "fsp-rich",
    "rating": 1500,
    "ranks": [{"discipline": "программирование", "rank": "1 разряд"}],
    "contests": [
        {"name": "Чемпионат ФСП 2026", "discipline": "программирование",
         "date": "2026-03-01", "place": 2, "diploma": 2, "team": False,
         "team_result": None},
        {"name": "Онлайн-этап", "discipline": "программирование",
         "date": "2025-09-01", "place": None, "diploma": None,
         "team": False, "team_result": None},
        {"name": "Онлайн-этап 2", "discipline": "программирование",
         "date": "2025-08-01", "place": None, "diploma": None,
         "team": False, "team_result": None},
    ],
    "events": [{"name": "День открытых дверей", "date": "2025-05-01",
                "role": "участник"}],
}
# score = 0.7 (диплом II) + 0.15 (участие 1) + 0.075 (участие 2,
# затухание ×0.5) + 0.05 (мероприятие) = 0.975
EXPECTED_SCORE = 0.975


def test_compute_fsp_score_formula():
    assert compute_fsp_score(RICH_PROFILE) == EXPECTED_SCORE
    # победа = 1.0; сумма побед упирается в cap 1.0
    assert compute_fsp_score({"contests": [{"place": 1}]}) == 1.0
    assert compute_fsp_score({"contests": [{"place": 1}, {"place": 1},
                                           {"place": 1}]}) == 1.0
    # призовое место без диплома — 0.5
    assert compute_fsp_score({"contests": [{"place": 3}]}) == 0.5
    # командный результат считаем как обычное достижение (Q&A)
    assert compute_fsp_score(
        {"contests": [{"place": None, "team_result": {"place": 1}}]}
    ) == 1.0
    # только явки: затухание 0.15 + 0.075 + 0.0375
    assert compute_fsp_score({"contests": [{}, {}, {}]}) == 0.2625
    assert compute_fsp_score(None) == 0.0
    assert compute_fsp_score({}) == 0.0


async def test_fsp_link_with_history(client, fake_core, fake_fsp):
    fake_fsp.profiles = {"fsp-rich": RICH_PROFILE}
    headers, user = await make_candidate(client)
    resp = await client.post(
        "/api/v1/candidate/fsp-link",
        json={"fsp_id": "fsp-rich"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["fsp_id"] == "fsp-rich"
    assert data["has_fsp"] is True
    assert data["fsp"]["score"] == EXPECTED_SCORE
    assert data["fsp"]["achievements"]["rating"] == 1500
    # снапшот в core с fsp_score (§4.3)
    pushes = [s for cid, s in fake_core.snapshots if cid == user["id"]]
    assert pushes[-1]["fsp_score"] == EXPECTED_SCORE


async def test_fsp_link_no_history_404(client, fake_core, fake_fsp):
    """Обязательный кейс ТЗ: реестр отвечает 404 → score 0, блок
    достижений не показывается, профиль и подборка корректны."""
    fake_fsp.profiles = {}  # любой fsp_id — 404
    headers, user = await make_candidate(client)
    resp = await client.post(
        "/api/v1/candidate/fsp-link",
        json={"fsp_id": "fsp-nobody"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["fsp_id"] == "fsp-nobody"
    assert data["has_fsp"] is False
    assert data["fsp"] is None
    pushes = [s for cid, s in fake_core.snapshots if cid == user["id"]]
    assert pushes[-1]["fsp_score"] == 0.0


async def test_fsp_link_taken_by_other_user_409(client, fake_fsp):
    fake_fsp.profiles = {}
    headers, _ = await make_candidate(client)
    other_headers, _ = await make_candidate(client)
    assert (
        await client.post(
            "/api/v1/candidate/fsp-link",
            json={"fsp_id": "fsp-1"}, headers=headers,
        )
    ).status_code == 200
    resp = await client.post(
        "/api/v1/candidate/fsp-link",
        json={"fsp_id": "fsp-1"}, headers=other_headers,
    )
    assert resp.status_code == 409


async def test_fsp_unlink_clears(client, fake_core, fake_fsp):
    fake_fsp.profiles = {"fsp-rich": RICH_PROFILE}
    headers, user = await make_candidate(client)
    await client.post(
        "/api/v1/candidate/fsp-link",
        json={"fsp_id": "fsp-rich"}, headers=headers,
    )
    resp = await client.delete(
        "/api/v1/candidate/fsp-link", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fsp_id"] is None
    assert data["fsp"] is None
    pushes = [s for cid, s in fake_core.snapshots if cid == user["id"]]
    assert pushes[-1]["fsp_score"] == 0.0


async def test_bank_fsp_filter_with_history(client, fake_fsp):
    """Фильтр «есть достижения ФСП» корректно включает/исключает."""
    fake_fsp.profiles = {"fsp-rich": RICH_PROFILE}
    rich_headers, _ = await make_candidate(client)
    await client.post(
        "/api/v1/candidate/fsp-link",
        json={"fsp_id": "fsp-rich"}, headers=rich_headers,
    )
    await make_candidate(client)  # без привязки
    from tests.conftest import make_employer

    emp_headers, _ = await make_employer(client)
    resp = await client.get(
        "/api/v1/employer/candidates", params={"fsp": "true"},
        headers=emp_headers,
    )
    assert len(resp.json()) == 1
    assert resp.json()[0]["profile"]["has_fsp"] is True
    assert resp.json()[0]["profile"]["fsp"]["score"] == EXPECTED_SCORE
    resp = await client.get(
        "/api/v1/employer/candidates", params={"fsp": "false"},
        headers=emp_headers,
    )
    assert len(resp.json()) == 1
