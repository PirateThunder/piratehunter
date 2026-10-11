"""Потребности работодателя: CRUD, владелец, валидация вилки."""

from tests.conftest import make_employer

NEED_BODY = {
    "raw_text": "Ищем backend middle на python с postgres",
    "stack_must": ["python", "postgresql"],
    "stack_nice": ["redis"],
    "spec_slug": "backend",
    "grade": "middle",
    "salary_from": 200000,
    "salary_to": 350000,
}


async def test_needs_crud(client):
    headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/employer/needs", json=NEED_BODY, headers=headers
    )
    assert resp.status_code == 201, resp.text
    need = resp.json()
    assert need["spec_slug"] == "backend"
    need_id = need["id"]

    resp = await client.get("/api/v1/employer/needs", headers=headers)
    assert [n["id"] for n in resp.json()] == [need_id]

    resp = await client.get(
        f"/api/v1/employer/needs/{need_id}", headers=headers
    )
    assert resp.json()["raw_text"] == NEED_BODY["raw_text"]

    resp = await client.put(
        f"/api/v1/employer/needs/{need_id}",
        json={**NEED_BODY, "grade": "senior"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["grade"] == "senior"

    resp = await client.delete(
        f"/api/v1/employer/needs/{need_id}", headers=headers
    )
    assert resp.status_code == 204
    resp = await client.get(
        f"/api/v1/employer/needs/{need_id}", headers=headers
    )
    assert resp.status_code == 404


async def test_needs_salary_range_422(client):
    headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/employer/needs",
        json={**NEED_BODY, "salary_from": 500000, "salary_to": 100000},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_needs_other_company_404(client):
    headers_a, _ = await make_employer(client)
    headers_b, _ = await make_employer(client, name="B")
    need_id = (
        await client.post(
            "/api/v1/employer/needs", json=NEED_BODY, headers=headers_a
        )
    ).json()["id"]
    for method, kwargs in (
        ("get", {}),
        ("put", {"json": NEED_BODY}),
        ("delete", {}),
    ):
        resp = await getattr(client, method)(
            f"/api/v1/employer/needs/{need_id}", headers=headers_b, **kwargs
        )
        assert resp.status_code == 404


async def test_needs_require_company_profile_404(client):
    from tests.conftest import register_via_email, select_role

    headers, _ = await register_via_email(client)
    await select_role(client, headers, "employer")
    resp = await client.post(
        "/api/v1/employer/needs", json=NEED_BODY, headers=headers
    )
    assert resp.status_code == 404


async def test_shortlist_core_error_502(client, fake_core):
    class DownCore(type(fake_core)):
        async def match(self, need):
            from app.core_client.client import CoreError

            raise CoreError("core-api недоступен")

    from app.core_client.client import get_core_client
    from app.main import app

    headers, _ = await make_employer(client)
    need_id = (
        await client.post(
            "/api/v1/employer/needs", json=NEED_BODY, headers=headers
        )
    ).json()["id"]
    app.dependency_overrides[get_core_client] = DownCore
    try:
        resp = await client.get(
            f"/api/v1/employer/needs/{need_id}/shortlist", headers=headers
        )
        assert resp.status_code == 502
    finally:
        app.dependency_overrides.pop(get_core_client, None)


# --- LLM-парсинг потребности (§7.3, «мы поняли так») ---

PARSE_RESULT = {
    "spec": "backend",
    "grade": "middle",
    "stack_must": ["python", "postgresql"],
    "stack_nice": ["redis"],
    "confidence": 0.87,
    "notes": "распознано по ключевым словам",
}


async def test_parse_need_proxy(client, fake_core):
    fake_core.parse_result = PARSE_RESULT
    headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/employer/needs/parse",
        json={"raw_text": "нужен бэкендер на python"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data == PARSE_RESULT
    assert fake_core.parse_calls == ["нужен бэкендер на python"]


async def test_parse_need_core_error_502(client, fake_core):
    fake_core.parse_error = True
    headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/employer/needs/parse",
        json={"raw_text": "что-нибудь"},
        headers=headers,
    )
    assert resp.status_code == 502


async def test_parse_need_candidate_403(client):
    from tests.conftest import make_candidate

    cand_headers, _ = await make_candidate(client)
    resp = await client.post(
        "/api/v1/employer/needs/parse",
        json={"raw_text": "что-нибудь"},
        headers=cand_headers,
    )
    assert resp.status_code == 403


async def test_create_auto_parse_fills_empty_fields(client, fake_core):
    """spec_slug не указан → авто-парсинг: поля из parsed, сам parsed
    сохранён для UI «мы поняли так»."""
    fake_core.parse_result = PARSE_RESULT
    headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/employer/needs",
        json={"raw_text": "ищем python middle"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    need = resp.json()
    assert need["spec_slug"] == "backend"
    assert need["grade"] == "middle"
    assert need["stack_must"] == ["python", "postgresql"]
    assert need["stack_nice"] == ["redis"]
    assert need["parsed"]["confidence"] == 0.87


async def test_create_explicit_spec_not_overwritten(client, fake_core):
    """spec задан явно → парсинг сохраняется в parsed, но поля НЕ
    перетираются (явный выбор работодателя важнее LLM)."""
    fake_core.parse_result = {**PARSE_RESULT, "spec": "frontend",
                              "grade": "senior"}
    headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/employer/needs",
        json={**NEED_BODY, "stack_must": ["go"]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    need = resp.json()
    assert need["spec_slug"] == "backend"  # из NEED_BODY, не из парсинга
    assert need["grade"] == "middle"
    assert need["stack_must"] == ["go"]
    assert need["parsed"]["spec"] == "frontend"  # «мы поняли так» сохранено


async def test_create_parse_garbage_ignored(client, fake_core):
    """core вернул несправочные значения — подстановки нет, parsed
    сохранён как есть."""
    fake_core.parse_result = {**PARSE_RESULT, "spec": "космолётчик",
                              "grade": "god-mode"}
    headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/employer/needs",
        json={"raw_text": "непонятный текст"},
        headers=headers,
    )
    assert resp.status_code == 201
    need = resp.json()
    assert need["spec_slug"] is None
    assert need["grade"] is None
    assert need["parsed"]["spec"] == "космолётчик"


async def test_create_core_down_best_effort(client, fake_core):
    """core down → создание не падает, parsed=None."""
    fake_core.parse_error = True
    headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/employer/needs",
        json={"raw_text": "ищем python middle"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    need = resp.json()
    assert need["parsed"] is None
    assert need["spec_slug"] is None
