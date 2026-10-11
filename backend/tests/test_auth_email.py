"""Вход по коду из письма (§7.1): request/verify, dev_code при
BACK_ENV=local без SMTP, лимиты, find-or-create, refresh."""

from app.config import get_settings

EMAIL = "Judge@Test.dev"
EMAIL_NORM = "judge@test.dev"


async def _request(client, email: str = EMAIL, headers: dict | None = None):
    return await client.post(
        "/api/v1/auth/email/request", json={"email": email}, headers=headers
    )


async def _verify(client, code: str, email: str = EMAIL,
                  headers: dict | None = None):
    return await client.post(
        "/api/v1/auth/email/verify",
        json={"email": email, "code": code},
        headers=headers,
    )


async def test_request_202_and_dev_code_in_local(client):
    resp = await _request(client)
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["detail"]
    # BACK_ENV=local и без SMTP — код возвращается в dev_code
    assert data["dev_code"] is not None
    assert len(data["dev_code"]) == 6


async def test_request_bad_email_422(client):
    resp = await _request(client, "not-an-email")
    assert resp.status_code == 422


async def test_verify_creates_user_and_logs_in(client):
    code = (await _request(client)).json()["dev_code"]
    resp = await _verify(client, code)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user"]["email"] == EMAIL_NORM
    assert data["user"]["role"] is None  # роль — на онбординге
    assert data["user"]["is_verified"] is True
    assert resp.cookies.get("ph_refresh")
    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL_NORM


async def test_verify_second_login_same_user(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "email_code_cooldown", 0)
    first_code = (await _request(client)).json()["dev_code"]
    first = (await _verify(client, first_code)).json()
    second_code = (await _request(client)).json()["dev_code"]
    second = (await _verify(client, second_code)).json()
    assert second["user"]["id"] == first["user"]["id"]


async def test_verify_without_request_401(client):
    resp = await _verify(client, "123456")
    assert resp.status_code == 401
    assert "не запрошен" in resp.json()["detail"]


async def test_verify_wrong_code_401_then_right_ok(client):
    code = (await _request(client)).json()["dev_code"]
    resp = await _verify(client, "000000")
    assert resp.status_code == 401
    assert "неверный код" in resp.json()["detail"]
    assert (await _verify(client, code)).status_code == 200


async def test_verify_attempts_exhausted_burns_code(client):
    code = (await _request(client)).json()["dev_code"]
    for _ in range(5):
        assert (await _verify(client, "000000")).status_code == 401
    # попытки кончились — код сгорел, даже верный не принимается
    assert (await _verify(client, code)).status_code == 401


async def test_request_cooldown_429(client):
    assert (await _request(client)).status_code == 202
    resp = await _request(client)
    assert resp.status_code == 429


async def test_request_daily_email_cap_429(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "email_code_cooldown", 0)
    monkeypatch.setattr(get_settings(), "email_code_daily_per_email", 3)
    for _ in range(3):
        assert (await _request(client)).status_code == 202
    assert (await _request(client)).status_code == 429


async def test_refresh_rotates_pair(client):
    code = (await _request(client)).json()["dev_code"]
    first = (await _verify(client, code)).json()
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200, resp.text
    second = resp.json()
    assert second["user"]["id"] == first["user"]["id"]
    assert second["access_token"] != first["access_token"]


async def test_refresh_without_cookie_401(client):
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_verify_bearer_links_email_to_current_user(client, dev_login_on):
    """Залогиненный (FSP/dev) юзер проходит verify с Bearer — почта
    привязывается к нему, новый аккаунт не создаётся."""
    resp = await client.post(
        "/api/v1/auth/dev", json={"account": "candidate"}
    )
    dev_user = resp.json()["user"]
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    code = (await _request(client)).json()["dev_code"]
    resp = await _verify(client, code, headers=headers)
    assert resp.status_code == 409  # у демо-аккаунта уже есть почта
    # привяжем свежую почту к свежему FSP-входу без email
    resp = await client.get("/api/v1/auth/fsp/authorize")
    state = resp.json()["state"]
    resp = await client.post(
        "/api/v1/auth/fsp/callback", json={"code": "c1", "state": state}
    )
    fsp_user = resp.json()["user"]
    assert fsp_user["email"] is None
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    code = (await _request(client, "new@test.dev")).json()["dev_code"]
    resp = await _verify(client, code, email="new@test.dev", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["id"] == fsp_user["id"]
    assert resp.json()["user"]["email"] == "new@test.dev"
    assert dev_user["id"] != fsp_user["id"]
