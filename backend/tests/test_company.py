"""Профиль компании и справочник каталога (прокси core)."""

from tests.conftest import COMPANY_BODY, make_employer


async def test_company_put_get(client):
    headers, _ = await make_employer(client)
    resp = await client.get("/api/v1/employer/company", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == COMPANY_BODY["name"]
    resp = await client.put(
        "/api/v1/employer/company",
        json={**COMPANY_BODY, "name": "Новое имя"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Новое имя"


async def test_company_get_404_before_fill(client):
    from tests.conftest import register_via_email, select_role

    headers, _ = await register_via_email(client)
    await select_role(client, headers, "employer")
    resp = await client.get("/api/v1/employer/company", headers=headers)
    assert resp.status_code == 404


async def test_catalog_proxy_and_cache(client, fake_core):
    resp = await client.get("/api/v1/catalog")
    assert resp.status_code == 200
    assert resp.json()["grades"] == ["intern", "junior", "middle", "senior"]
    assert fake_core.catalog_calls == 1
    # второй запрос — из кэша, core не дёргаем (§6: backend кэширует)
    resp = await client.get("/api/v1/catalog")
    assert resp.status_code == 200
    assert fake_core.catalog_calls == 1
