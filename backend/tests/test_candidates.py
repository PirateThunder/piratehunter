"""Профиль кандидата: upsert, валидация, банк с фильтрами."""

from tests.conftest import make_candidate, make_employer


async def test_put_profile_creates_then_updates(client):
    headers, _ = await make_candidate(client, about="v1")
    resp = await client.get("/api/v1/candidate/profile", headers=headers)
    assert resp.json()["about"] == "v1"
    from tests.conftest import PROFILE_BODY

    resp = await client.put(
        "/api/v1/candidate/profile",
        json={**PROFILE_BODY, "about": "v2", "fio": "Иван Сидоров"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["about"] == "v2"
    assert resp.json()["fio"] == "Иван Сидоров"


async def test_profile_get_empty_draft_before_fill(client):
    """Новый кандидат: GET отдаёт 200 с пустым черновиком (иначе клиенты
    висят на 404-бесконечном лоадере)."""
    from tests.conftest import register_via_email, select_role

    headers, user = await register_via_email(client)
    await select_role(client, headers, "candidate")
    resp = await client.get("/api/v1/candidate/profile", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate_id"] == user["id"]
    assert data["fio"] == ""
    assert data["spec_slug"] is None
    assert data["stack"] == []


async def test_grade_get_unverified_before_fill(client):
    """Новый кандидат без профиля: грейд «unverified», без 404."""
    from tests.conftest import register_via_email, select_role

    headers, _ = await register_via_email(client)
    await select_role(client, headers, "candidate")
    resp = await client.get("/api/v1/candidate/grade", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unverified"
    assert data["grade_verified"] is None
    assert data["category_rank"] is None


async def test_profile_validation_422(client):
    from tests.conftest import PROFILE_BODY, register_via_email, select_role

    headers, _ = await register_via_email(client)
    await select_role(client, headers, "candidate")
    bad = {**PROFILE_BODY, "grade_claimed": "god-mode"}
    resp = await client.put(
        "/api/v1/candidate/profile", json=bad, headers=headers
    )
    assert resp.status_code == 422


async def test_bank_filters(client):
    await make_candidate(client)  # backend, python
    await make_candidate(
        client,
        spec_slug="frontend",
        stack=["react", "typescript"],
        fio="Фронтендер",
    )
    emp_headers, _ = await make_employer(client)
    # все
    resp = await client.get("/api/v1/employer/candidates", headers=emp_headers)
    assert len(resp.json()) == 2
    # по специализации
    resp = await client.get(
        "/api/v1/employer/candidates", params={"spec": "backend"},
        headers=emp_headers,
    )
    assert len(resp.json()) == 1
    assert resp.json()[0]["profile"]["spec_slug"] == "backend"
    # по стеку (все перечисленные обязательны)
    resp = await client.get(
        "/api/v1/employer/candidates", params={"stack": "python,redis"},
        headers=emp_headers,
    )
    assert len(resp.json()) == 1
    resp = await client.get(
        "/api/v1/employer/candidates", params={"stack": "python,react"},
        headers=emp_headers,
    )
    assert len(resp.json()) == 0
    # без подтверждённого грейда — категория unverified (§6)
    resp = await client.get(
        "/api/v1/employer/candidates", params={"grade": "unverified"},
        headers=emp_headers,
    )
    assert len(resp.json()) == 2
    resp = await client.get(
        "/api/v1/employer/candidates", params={"grade": "middle"},
        headers=emp_headers,
    )
    assert len(resp.json()) == 0
    # category = spec:grade
    resp = await client.get(
        "/api/v1/employer/candidates",
        params={"category": "backend:unverified"},
        headers=emp_headers,
    )
    assert len(resp.json()) == 1
    # фильтр ФСП: ни у кого истории нет
    resp = await client.get(
        "/api/v1/employer/candidates", params={"fsp": "true"},
        headers=emp_headers,
    )
    assert len(resp.json()) == 0


async def test_snapshot_pushed_on_profile_update(client, fake_core):
    _, user = await make_candidate(client)
    pushes = [s for cid, s in fake_core.snapshots if cid == user["id"]]
    assert pushes, "PUT профиля обязан пушить снапшот в core (§4.3)"
    snap = pushes[-1]
    assert snap["spec"] == "backend"
    assert snap["stack"] == ["python", "postgresql", "redis"]
    assert snap["fsp_score"] == 0.0
    # ПДн в снапшоте нет (privacy by design, §4.2)
    assert "fio" not in snap and "phone" not in snap
