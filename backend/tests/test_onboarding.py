"""Онбординг: выбор роли один раз + согласия 152-ФЗ (§7.1)."""

from tests.conftest import register_via_email


async def test_role_select_sets_role_and_consents(client):
    headers, user = await register_via_email(client)
    resp = await client.post(
        "/api/v1/users/me/role",
        json={"role": "candidate", "consent_pd": True,
              "consent_publish": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "candidate"
    assert data["consent_pd"] is True
    assert data["consent_publish"] is True


async def test_role_select_twice_409(client):
    headers, _ = await register_via_email(client)
    body = {"role": "candidate", "consent_pd": True}
    assert (
        await client.post(
            "/api/v1/users/me/role", json=body, headers=headers
        )
    ).status_code == 200
    resp = await client.post(
        "/api/v1/users/me/role",
        json={"role": "employer", "consent_pd": True},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_role_select_requires_pd_consent_422(client):
    headers, _ = await register_via_email(client)
    resp = await client.post(
        "/api/v1/users/me/role",
        json={"role": "candidate", "consent_pd": False},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_candidate_area_forbidden_without_role(client):
    headers, _ = await register_via_email(client)
    resp = await client.get("/api/v1/candidate/profile", headers=headers)
    assert resp.status_code == 403


async def test_employer_area_forbidden_for_candidate(client):
    headers, _ = await register_via_email(client)
    await client.post(
        "/api/v1/users/me/role",
        json={"role": "candidate", "consent_pd": True},
        headers=headers,
    )
    resp = await client.get("/api/v1/employer/company", headers=headers)
    assert resp.status_code == 403


async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401
