"""Dev-login фиксированными демо-аккаунтами (BACK_AUTH_DEV_LOGIN=1)."""


async def test_dev_login_off_404(client):
    resp = await client.post("/api/v1/auth/dev", json={"account": "candidate"})
    assert resp.status_code == 404


async def test_dev_login_candidate(client, dev_login_on):
    resp = await client.post("/api/v1/auth/dev", json={"account": "candidate"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user"]["role"] == "candidate"
    assert data["user"]["email"] == "demo-candidate@ph.dev"
    assert data["user"]["fsp_id"] is None


async def test_dev_login_candidate_fsp(client, dev_login_on):
    resp = await client.post(
        "/api/v1/auth/dev", json={"account": "candidate-fsp"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["fsp_id"] == "fsp_001"


async def test_dev_login_employer_idempotent(client, dev_login_on):
    first = (
        await client.post("/api/v1/auth/dev", json={"account": "employer"})
    ).json()
    second = (
        await client.post("/api/v1/auth/dev", json={"account": "employer"})
    ).json()
    assert first["user"]["role"] == "employer"
    assert second["user"]["id"] == first["user"]["id"]


async def test_dev_login_unknown_account_422(client, dev_login_on):
    resp = await client.post("/api/v1/auth/dev", json={"account": "root"})
    assert resp.status_code == 422
