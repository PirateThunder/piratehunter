"""Вход через FSP ID (мок-OIDC, §7.1): authorize → callback → token →
userinfo → find-or-create по sub (fsp_id)."""


async def test_authorize_returns_url_and_state(client, fake_fsp):
    resp = await client.get("/api/v1/auth/fsp/authorize")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["authorize_url"].startswith("http://fsp.test/oidc/authorize")
    assert data["state"]
    assert fake_fsp.authorize_calls == [(data["state"], None)]


async def test_callback_creates_user_by_fsp_id(client, fake_fsp):
    state = (await client.get("/api/v1/auth/fsp/authorize")).json()["state"]
    resp = await client.post(
        "/api/v1/auth/fsp/callback", json={"code": "code-1", "state": state}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user"]["fsp_id"] == "fsp-user-1"
    assert data["user"]["role"] is None  # роль — на онбординге
    assert fake_fsp.exchanged == ["code-1"]
    assert resp.cookies.get("ph_refresh")


async def test_callback_second_login_same_user(client, fake_fsp):
    state = (await client.get("/api/v1/auth/fsp/authorize")).json()["state"]
    first = (
        await client.post(
            "/api/v1/auth/fsp/callback",
            json={"code": "c1", "state": state},
        )
    ).json()
    state = (await client.get("/api/v1/auth/fsp/authorize")).json()["state"]
    second = (
        await client.post(
            "/api/v1/auth/fsp/callback",
            json={"code": "c2", "state": state},
        )
    ).json()
    assert second["user"]["id"] == first["user"]["id"]


async def test_callback_bad_state_401(client):
    resp = await client.post(
        "/api/v1/auth/fsp/callback",
        json={"code": "c1", "state": "forged-state"},
    )
    assert resp.status_code == 401


async def test_callback_state_is_one_time(client, fake_fsp):
    state = (await client.get("/api/v1/auth/fsp/authorize")).json()["state"]
    body = {"code": "c1", "state": state}
    assert (
        await client.post("/api/v1/auth/fsp/callback", json=body)
    ).status_code == 200
    # повтор с тем же state — 401 (state одноразовый)
    resp = await client.post("/api/v1/auth/fsp/callback", json=body)
    assert resp.status_code == 401


async def test_authorize_with_explicit_fsp_id(client, fake_fsp):
    resp = await client.get(
        "/api/v1/auth/fsp/authorize", params={"fsp_id": "fsp-42"}
    )
    assert resp.status_code == 200
    assert fake_fsp.authorize_calls == [(resp.json()["state"], "fsp-42")]


async def test_get_callback_redirects_with_refresh_cookie(client, fake_fsp):
    """Browser flow: реестр вернул code+state на GET-callback → 303 на
    /login/callback фронта + refresh-cookie (сессию поднимет bootstrap)."""
    state = (await client.get("/api/v1/auth/fsp/authorize")).json()["state"]
    resp = await client.get(
        "/api/v1/auth/fsp/callback",
        params={"code": "code-1", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    assert resp.headers["location"].endswith("/login/callback")
    assert "ph_refresh=" in resp.headers.get("set-cookie", "")
    assert fake_fsp.exchanged == ["code-1"]


async def test_get_callback_bad_state_redirects_to_login(client):
    resp = await client.get(
        "/api/v1/auth/fsp/callback",
        params={"code": "c1", "state": "forged-state"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/login" in resp.headers["location"]
    assert "error=fsp" in resp.headers["location"]

