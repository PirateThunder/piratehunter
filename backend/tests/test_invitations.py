"""Приглашения: обязательная вилка ЗП (ТЗ §2.2), переходы статусов,
лимит создания, доступы."""

from app.config import get_settings
from tests.conftest import make_candidate, make_employer, make_invitation


async def test_create_requires_salary_422(client):
    _, cand_user = await make_candidate(client)
    emp_headers, _ = await make_employer(client)
    body = {
        "candidate_id": cand_user["id"],
        "text": "позиция",
        "contact_method": "email",
        # вилки нет вообще — 422 (приглашение без ЗП отклоняется, §16.2)
    }
    resp = await client.post(
        "/api/v1/employer/invitations", json=body, headers=emp_headers
    )
    assert resp.status_code == 422


async def test_create_salary_range_validated_422(client):
    _, cand_user = await make_candidate(client)
    emp_headers, _ = await make_employer(client)
    body = {
        "candidate_id": cand_user["id"],
        "text": "позиция",
        "salary_from": 300000,
        "salary_to": 200000,
        "salary_type": "gross",
        "contact_method": "email",
    }
    resp = await client.post(
        "/api/v1/employer/invitations", json=body, headers=emp_headers
    )
    assert resp.status_code == 422


async def test_create_salary_type_required_422(client):
    _, cand_user = await make_candidate(client)
    emp_headers, _ = await make_employer(client)
    body = {
        "candidate_id": cand_user["id"],
        "text": "позиция",
        "salary_from": 100000,
        "salary_to": 200000,
        "salary_type": "brutto",  # только gross|net
        "contact_method": "email",
    }
    resp = await client.post(
        "/api/v1/employer/invitations", json=body, headers=emp_headers
    )
    assert resp.status_code == 422


async def test_create_unknown_candidate_404(client):
    emp_headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/employer/invitations",
        json={
            "candidate_id": "no-such-id",
            "text": "позиция",
            "salary_from": 100000,
            "salary_to": 200000,
            "salary_type": "net",
            "contact_method": "email",
        },
        headers=emp_headers,
    )
    assert resp.status_code == 404


async def test_create_forbidden_for_candidate_role(client):
    cand_headers, cand_user = await make_candidate(client)
    resp = await client.post(
        "/api/v1/employer/invitations",
        json={
            "candidate_id": cand_user["id"],
            "text": "позиция",
            "salary_from": 100000,
            "salary_to": 200000,
            "salary_type": "net",
            "contact_method": "email",
        },
        headers=cand_headers,
    )
    assert resp.status_code == 403


async def test_statuses_flow_sent_viewed_accepted(client):
    cand_headers, cand_user = await make_candidate(client)
    emp_headers, _ = await make_employer(client)
    invitation = await make_invitation(client, emp_headers, cand_user["id"])
    assert invitation["status"] == "sent"
    # кандидат открыл список → viewed
    items = (
        await client.get(
            "/api/v1/candidate/invitations", headers=cand_headers
        )
    ).json()
    assert items[0]["status"] == "viewed"
    # работодатель видит тот же статус
    items = (
        await client.get("/api/v1/employer/invitations", headers=emp_headers)
    ).json()
    assert items[0]["status"] == "viewed"
    # accept
    resp = await client.post(
        f"/api/v1/candidate/invitations/{invitation['id']}/accept",
        headers=cand_headers,
    )
    assert resp.status_code == 200
    # повторный ответ — 409
    resp = await client.post(
        f"/api/v1/candidate/invitations/{invitation['id']}/decline",
        headers=cand_headers,
    )
    assert resp.status_code == 409


async def test_decline_flow(client):
    cand_headers, cand_user = await make_candidate(client)
    emp_headers, _ = await make_employer(client)
    invitation = await make_invitation(client, emp_headers, cand_user["id"])
    resp = await client.post(
        f"/api/v1/candidate/invitations/{invitation['id']}/decline",
        headers=cand_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"
    # после decline контакты компании НЕ раскрыты
    assert resp.json()["company"]["contacts"] is None
    resp = await client.post(
        f"/api/v1/candidate/invitations/{invitation['id']}/accept",
        headers=cand_headers,
    )
    assert resp.status_code == 409


async def test_invitation_rate_limit_429(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "invitation_rate_per_hour", 1)
    _, cand_user = await make_candidate(client)
    emp_headers, _ = await make_employer(client)
    await make_invitation(client, emp_headers, cand_user["id"])
    resp = await client.post(
        "/api/v1/employer/invitations",
        json={
            "candidate_id": cand_user["id"],
            "text": "ещё одна",
            "salary_from": 100000,
            "salary_to": 200000,
            "salary_type": "gross",
            "contact_method": "email",
        },
        headers=emp_headers,
    )
    assert resp.status_code == 429


async def test_employer_sees_only_own_invitations(client):
    _, cand_user = await make_candidate(client)
    emp_a, _ = await make_employer(client)
    emp_b, _ = await make_employer(client, name="B")
    await make_invitation(client, emp_a, cand_user["id"])
    resp = await client.get("/api/v1/employer/invitations", headers=emp_b)
    assert resp.json() == []
