from urllib.parse import parse_qs, urlparse

import jwt

from app.config import get_settings
from app.oidc.constants import DEMO_FSP_ID, IDENTITIES

CLIENT_ID = get_settings().oidc_client_id
REDIRECT_URI = "http://backend.test/api/v1/auth/fsp/callback"
USER = IDENTITIES[2]  # детерминированная личность для флоу


def _authorize_params(**extra):
    return {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid",
        "state": "test-state-42",
        **extra,
    }


async def _authorize_code(client, fsp_id: str) -> str:
    resp = await client.get(
        "/oidc/authorize",
        params=_authorize_params(login_hint=fsp_id),
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = urlparse(resp.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT_URI
    query = parse_qs(location.query)
    assert query["state"] == ["test-state-42"]
    return query["code"][0]


async def test_full_oidc_flow(client):
    code = await _authorize_code(client, USER.fsp_id)

    token_resp = await client.post(
        "/oidc/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
        },
    )
    assert token_resp.status_code == 200
    tokens = token_resp.json()
    assert tokens["token_type"] == "Bearer"
    assert tokens["expires_in"] > 0

    settings = get_settings()
    id_claims = jwt.decode(
        tokens["id_token"],
        settings.jwt_secret,
        algorithms=["HS256"],
        audience=CLIENT_ID,
    )
    assert id_claims["sub"] == USER.fsp_id
    assert id_claims["name"] == USER.name
    assert id_claims["email"] == USER.email
    assert id_claims["iss"] == settings.issuer

    info_resp = await client.get(
        "/oidc/userinfo",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert info_resp.status_code == 200
    assert info_resp.json() == {
        "sub": USER.fsp_id,
        "name": USER.name,
        "email": USER.email,
        "email_verified": True,
    }


async def test_authorize_shows_form_without_login_hint(client):
    resp = await client.get("/oidc/authorize", params=_authorize_params())
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "FSP ID" in resp.text
    for identity in IDENTITIES:
        assert identity.fsp_id in resp.text


async def test_code_is_single_use(client):
    code = await _authorize_code(client, USER.fsp_id)
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
    }
    assert (await client.post("/oidc/token", data=form)).status_code == 200
    second = await client.post("/oidc/token", data=form)
    assert second.status_code == 400
    assert second.json()["error"] == "invalid_grant"


async def test_token_rejects_unknown_code(client):
    resp = await client.post(
        "/oidc/token",
        data={
            "grant_type": "authorization_code",
            "code": "no-such-code",
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_grant"


async def test_token_rejects_redirect_uri_mismatch(client):
    code = await _authorize_code(client, USER.fsp_id)
    resp = await client.post(
        "/oidc/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://evil.test/callback",
            "client_id": CLIENT_ID,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_grant"


async def test_authorize_rejects_unknown_client(client):
    resp = await client.get(
        "/oidc/authorize",
        params=_authorize_params(client_id="someone-else", login_hint=USER.fsp_id),
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_client"


async def test_authorize_rejects_wrong_response_type(client):
    resp = await client.get(
        "/oidc/authorize",
        params=_authorize_params(response_type="token"),
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "unsupported_response_type"


async def test_userinfo_requires_bearer(client):
    assert (await client.get("/oidc/userinfo")).status_code == 401
    bad = await client.get("/oidc/userinfo", headers={"Authorization": "Bearer garbage"})
    assert bad.status_code == 401
    assert bad.json()["error"] == "invalid_token"


async def test_id_token_is_not_an_access_token(client):
    code = await _authorize_code(client, USER.fsp_id)
    tokens = (
        await client.post(
            "/oidc/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
            },
        )
    ).json()
    resp = await client.get(
        "/oidc/userinfo",
        headers={"Authorization": f"Bearer {tokens['id_token']}"},
    )
    assert resp.status_code == 401


async def test_discovery_document(client):
    resp = await client.get("/.well-known/openid-configuration")
    assert resp.status_code == 200
    body = resp.json()
    issuer = get_settings().issuer
    assert body["issuer"] == issuer
    assert body["authorization_endpoint"] == f"{issuer}/oidc/authorize"
    assert body["token_endpoint"] == f"{issuer}/oidc/token"
    assert body["userinfo_endpoint"] == f"{issuer}/oidc/userinfo"
    assert body["response_types_supported"] == ["code"]


def test_demo_identity_exists():
    assert any(i.fsp_id == DEMO_FSP_ID for i in IDENTITIES)
