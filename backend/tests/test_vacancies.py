"""Вакансии и отклики (§7.7): CRUD, публикация/закрытие, ATS-
идемпотентность external_id, apply, статусы откликов, фильтры."""

from tests.conftest import make_candidate, make_employer

VACANCY_BODY = {
    "title": "Backend-разработчик (Python)",
    "description": "API платформы, FastAPI, PostgreSQL.",
    "spec_slug": "backend",
    "grade": "middle",
    "stack_must": ["python", "fastapi"],
    "stack_nice": ["redis"],
    "salary_from": 250000,
    "salary_to": 400000,
    "salary_type": "gross",
}


async def _create(client, headers, **overrides):
    resp = await client.post(
        "/api/v1/employer/vacancies",
        json={**VACANCY_BODY, **overrides},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_vacancy_crud_lifecycle(client):
    headers, _ = await make_employer(client)
    vacancy = await _create(client, headers)
    assert vacancy["status"] == "draft"
    assert vacancy["published_at"] is None

    resp = await client.get("/api/v1/employer/vacancies", headers=headers)
    assert [v["id"] for v in resp.json()] == [vacancy["id"]]

    resp = await client.put(
        f"/api/v1/employer/vacancies/{vacancy['id']}",
        json={**VACANCY_BODY, "title": "Senior backend"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Senior backend"

    resp = await client.post(
        f"/api/v1/employer/vacancies/{vacancy['id']}/publish",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"
    assert resp.json()["published_at"] is not None

    resp = await client.post(
        f"/api/v1/employer/vacancies/{vacancy['id']}/publish",
        headers=headers,
    )
    assert resp.status_code == 409

    resp = await client.post(
        f"/api/v1/employer/vacancies/{vacancy['id']}/close",
        headers=headers,
    )
    assert resp.json()["status"] == "closed"
    assert resp.json()["closed_at"] is not None

    # из closed можно переопубликовать
    resp = await client.post(
        f"/api/v1/employer/vacancies/{vacancy['id']}/publish",
        headers=headers,
    )
    assert resp.json()["status"] == "published"

    resp = await client.delete(
        f"/api/v1/employer/vacancies/{vacancy['id']}", headers=headers
    )
    assert resp.status_code == 204
    resp = await client.get("/api/v1/employer/vacancies", headers=headers)
    assert resp.json() == []


async def test_vacancy_external_id_idempotent(client):
    """Повторный POST с тем же external_id → 200 и обновление
    (ATS-идемпотентность, §17), дубля нет."""
    headers, _ = await make_employer(client)
    first = await _create(client, headers, external_id="ats-42")
    resp = await client.post(
        "/api/v1/employer/vacancies",
        json={**VACANCY_BODY, "title": "Обновлённый тайтл",
              "external_id": "ats-42"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == first["id"]
    assert resp.json()["title"] == "Обновлённый тайтл"
    resp = await client.get("/api/v1/employer/vacancies", headers=headers)
    assert len(resp.json()) == 1


async def test_vacancy_validation_422(client):
    headers, _ = await make_employer(client)
    for bad in (
        {"salary_from": 400000, "salary_to": 250000},
        {"salary_type": "brutto"},
        {"grade": "god"},
        {"spec_slug": "astrologer"},
    ):
        resp = await client.post(
            "/api/v1/employer/vacancies",
            json={**VACANCY_BODY, **bad},
            headers=headers,
        )
        assert resp.status_code == 422, bad


async def test_vacancy_other_company_404(client):
    headers_a, _ = await make_employer(client)
    headers_b, _ = await make_employer(client, name="B")
    vacancy = await _create(client, headers_a)
    for method, kwargs in (
        ("put", {"json": VACANCY_BODY}),
        ("delete", {}),
        ("post", {}),
    ):
        url = f"/api/v1/employer/vacancies/{vacancy['id']}"
        if method == "post":
            url += "/publish"
        resp = await getattr(client, method)(url, headers=headers_b,
                                             **kwargs)
        assert resp.status_code == 404


async def test_public_vacancies_filters_and_applied_flag(client):
    emp_headers, _ = await make_employer(client)
    vacancy = await _create(client, emp_headers)
    await _create(client, emp_headers, title="Черновик")
    await client.post(
        f"/api/v1/employer/vacancies/{vacancy['id']}/publish",
        headers=emp_headers,
    )
    cand_headers, _ = await make_candidate(client)

    # draft не виден кандидатам
    resp = await client.get("/api/v1/vacancies", headers=cand_headers)
    assert [v["title"] for v in resp.json()] == [
        "Backend-разработчик (Python)"
    ]
    # фильтры
    resp = await client.get(
        "/api/v1/vacancies", params={"spec": "backend", "grade": "middle",
                                     "stack": "python", "salary_from": 300000},
        headers=cand_headers,
    )
    assert len(resp.json()) == 1
    resp = await client.get(
        "/api/v1/vacancies", params={"salary_from": 500000},
        headers=cand_headers,
    )
    assert resp.json() == []
    resp = await client.get(
        "/api/v1/vacancies", params={"stack": "python,kubernetes"},
        headers=cand_headers,
    )
    assert resp.json() == []
    # карточка: компания без контактов, вилка видна
    card = (await client.get(
        "/api/v1/vacancies", headers=cand_headers
    )).json()[0]
    assert card["company"]["name"] == "ООО Рога и копыта"
    assert "contacts" not in card["company"]
    assert card["salary_type"] == "gross"
    assert card["already_applied"] is False

    # apply → already_applied
    resp = await client.post(
        f"/api/v1/vacancies/{vacancy['id']}/apply",
        json={"message": "Готов обсудить"},
        headers=cand_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "sent"
    card = (await client.get(
        "/api/v1/vacancies", headers=cand_headers
    )).json()[0]
    assert card["already_applied"] is True


async def test_apply_duplicate_409_and_unpublished_404(client):
    emp_headers, _ = await make_employer(client)
    vacancy = await _create(client, emp_headers)  # draft
    cand_headers, _ = await make_candidate(client)
    resp = await client.post(
        f"/api/v1/vacancies/{vacancy['id']}/apply",
        json={}, headers=cand_headers,
    )
    assert resp.status_code == 404
    await client.post(
        f"/api/v1/employer/vacancies/{vacancy['id']}/publish",
        headers=emp_headers,
    )
    assert (
        await client.post(
            f"/api/v1/vacancies/{vacancy['id']}/apply",
            json={}, headers=cand_headers,
        )
    ).status_code == 201
    resp = await client.post(
        f"/api/v1/vacancies/{vacancy['id']}/apply",
        json={}, headers=cand_headers,
    )
    assert resp.status_code == 409


async def test_employer_applications_viewed_and_patch(client):
    emp_headers, _ = await make_employer(client)
    cand_headers, _ = await make_candidate(client)
    vacancy = await _create(client, emp_headers)
    await client.post(
        f"/api/v1/employer/vacancies/{vacancy['id']}/publish",
        headers=emp_headers,
    )
    application_id = (
        await client.post(
            f"/api/v1/vacancies/{vacancy['id']}/apply",
            json={"message": "привет"}, headers=cand_headers,
        )
    ).json()["id"]

    # первый GET списка → sent превращается в viewed (как у приглашений)
    resp = await client.get(
        f"/api/v1/employer/vacancies/{vacancy['id']}/applications",
        headers=emp_headers,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "viewed"
    # контакты кандидата видны (он сам инициировал контакт)
    assert items[0]["candidate"]["contacts"] is not None
    assert items[0]["candidate"]["contacts"]["phone"] == "+7 900 111-22-33"

    # PATCH invited
    resp = await client.patch(
        f"/api/v1/employer/applications/{application_id}",
        json={"status": "invited"}, headers=emp_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "invited"

    # кандидат видит invited → контакты компании раскрыты
    resp = await client.get(
        "/api/v1/candidate/applications", headers=cand_headers
    )
    mine = resp.json()[0]
    assert mine["status"] == "invited"
    assert mine["vacancy"]["title"] == "Backend-разработчик (Python)"
    assert mine["company"]["contacts"]["contacts"]["hr_email"] == (
        "hr@roga.dev"
    )


async def test_patch_application_other_company_404(client):
    emp_a, _ = await make_employer(client)
    emp_b, _ = await make_employer(client, name="B")
    cand_headers, _ = await make_candidate(client)
    vacancy = await _create(client, emp_a)
    await client.post(
        f"/api/v1/employer/vacancies/{vacancy['id']}/publish",
        headers=emp_a,
    )
    application_id = (
        await client.post(
            f"/api/v1/vacancies/{vacancy['id']}/apply",
            json={}, headers=cand_headers,
        )
    ).json()["id"]
    resp = await client.patch(
        f"/api/v1/employer/applications/{application_id}",
        json={"status": "rejected"}, headers=emp_b,
    )
    assert resp.status_code == 404


async def test_company_contacts_hidden_until_invited(client):
    emp_headers, _ = await make_employer(client)
    cand_headers, _ = await make_candidate(client)
    vacancy = await _create(client, emp_headers)
    await client.post(
        f"/api/v1/employer/vacancies/{vacancy['id']}/publish",
        headers=emp_headers,
    )
    await client.post(
        f"/api/v1/vacancies/{vacancy['id']}/apply",
        json={}, headers=cand_headers,
    )
    resp = await client.get(
        "/api/v1/candidate/applications", headers=cand_headers
    )
    assert resp.json()[0]["company"]["contacts"] is None
    assert "hr@roga.dev" not in str(resp.json())
