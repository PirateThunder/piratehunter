"""Рыночная аналитика вилок (§7.5.5): агрегация по потребностям и
приглашениям категории, точные перцентили, деградация без core."""

from app.core_client.client import CoreError
from tests.conftest import (
    make_candidate,
    make_employer,
    make_invitation,
)


async def _need(client, headers, salary_from, salary_to,
                spec="backend", grade="middle"):
    resp = await client.post(
        "/api/v1/employer/needs",
        json={
            "raw_text": f"нужен {spec} {grade}",
            "spec_slug": spec,
            "grade": grade,
            "salary_from": salary_from,
            "salary_to": salary_to,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _pass_test(client, headers, grade="middle"):
    """Кандидат подтверждает грейд тестом (фейк core: confirmed)."""
    session_id = (
        await client.post(
            "/api/v1/tests/sessions",
            json={"grade_target": grade},
            headers=headers,
        )
    ).json()["session_id"]
    resp = await client.post(
        f"/api/v1/tests/sessions/{session_id}/answers",
        json={"answer": 0},
        headers=headers,
    )
    assert resp.json()["result"]["outcome"] == "confirmed"


async def _dataset(client):
    """Категория backend×middle:
    - needs: (100k,200k), (200k,300k), (300k,400k), (400k,500k)
    - invitations: C1 (500k,600k) [claimed middle], C2 (150k,250k)
      [claimed junior, verified middle]
    - шум: need frontend×middle (700k,800k), приглашение C3
      frontend×senior (900k,999k) — не должны попасть в выборку.
    """
    emp_headers, _ = await make_employer(client)
    for f, t in ((100000, 200000), (200000, 300000),
                 (300000, 400000), (400000, 500000)):
        await _need(client, emp_headers, f, t)
    await _need(client, emp_headers, 700000, 800000,
                spec="frontend", grade="middle")

    c1_headers, c1 = await make_candidate(client)  # backend, claimed middle
    c2_headers, c2 = await make_candidate(client, grade_claimed="junior")
    await _pass_test(client, c2_headers)  # verified middle
    c3_headers, c3 = await make_candidate(
        client, spec_slug="frontend", grade_claimed="senior"
    )
    await make_invitation(client, emp_headers, c1["id"],
                          salary_from=500000, salary_to=600000)
    await make_invitation(client, emp_headers, c2["id"],
                          salary_from=150000, salary_to=250000)
    await make_invitation(client, emp_headers, c3["id"],
                          salary_from=900000, salary_to=999999)
    return emp_headers


async def test_market_salary_exact_percentiles(client, fake_core):
    emp_headers = await _dataset(client)
    fake_core.ranking = [{"candidate_id": f"c{i}"} for i in range(3)]
    resp = await client.get(
        "/api/v1/employer/market/salary",
        params={"spec": "backend", "grade": "middle"},
        headers=emp_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["spec"] == "backend" and data["grade"] == "middle"
    assert data["category_size"] == 3
    assert data["sample_needs"] == 4
    assert data["sample_invitations"] == 2
    # from: [100k,150k,200k,300k,400k,500k]
    assert data["from_p25"] == 162500
    assert data["from_p50"] == 250000
    assert data["from_p75"] == 375000
    # to: [200k,250k,300k,400k,500k,600k]
    assert data["to_p25"] == 262500
    assert data["to_p50"] == 350000
    assert data["to_p75"] == 475000


async def test_market_salary_empty_category(client, fake_core):
    emp_headers, _ = await make_employer(client)
    fake_core.ranking = []
    resp = await client.get(
        "/api/v1/employer/market/salary",
        params={"spec": "qa", "grade": "intern"},
        headers=emp_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["category_size"] == 0
    assert data["sample_needs"] == 0
    assert data["sample_invitations"] == 0
    assert data["from_p50"] is None and data["to_p50"] is None


async def test_market_salary_core_down_category_null(
    client, fake_core, monkeypatch
):
    emp_headers = await _dataset(client)

    async def boom(spec, grade):
        raise CoreError("core-api недоступен")

    monkeypatch.setattr(fake_core, "category_ranking", boom)
    resp = await client.get(
        "/api/v1/employer/market/salary",
        params={"spec": "backend", "grade": "middle"},
        headers=emp_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["category_size"] is None  # best-effort
    assert data["from_p50"] == 250000  # аналитика всё равно отвечает


async def test_market_salary_invalid_params_422(client):
    emp_headers, _ = await make_employer(client)
    resp = await client.get(
        "/api/v1/employer/market/salary",
        params={"spec": "astrologer", "grade": "middle"},
        headers=emp_headers,
    )
    assert resp.status_code == 422
    resp = await client.get(
        "/api/v1/employer/market/salary",
        params={"spec": "backend", "grade": "god"},
        headers=emp_headers,
    )
    assert resp.status_code == 422


async def test_market_salary_candidate_403(client):
    cand_headers, _ = await make_candidate(client)
    resp = await client.get(
        "/api/v1/employer/market/salary",
        params={"spec": "backend", "grade": "middle"},
        headers=cand_headers,
    )
    assert resp.status_code == 403
