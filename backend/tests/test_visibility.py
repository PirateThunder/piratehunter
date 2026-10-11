"""ПРАВИЛА ВИДИМОСТИ §7.6 — сердце механики. Контакты кандидата
(email/phone/ссылки) не утекают НИ В ОДНОМ эндпоинте до accept и
открываются после. Плюс зеркально: контакты компании кандидату.

Проверяемые поверхности: банк кандидатов, подборка (shortlist),
трекер приглашений работодателя, входящие кандидата, accept-ответ.
"""

from tests.conftest import (
    make_candidate,
    make_employer,
    make_invitation,
)

CONTACT_MARKERS = ("@ivan", "ivanpetrov", "+7 900", "user-")


def _assert_no_contacts(payload: dict, candidate_email: str) -> None:
    """Ни одного контактного поля/значения в сериализованном виде."""
    text = str(payload)
    assert "phone" not in text
    assert "@ivan" not in text
    assert "ivanpetrov" not in text
    assert candidate_email not in text
    assert payload.get("contacts") is None


async def _world(client, fake_core):
    """Кандидат + работодатель; match core отдаёт этого кандидата."""
    cand_headers, cand_user = await make_candidate(client)
    emp_headers, emp_user = await make_employer(client)
    fake_core.match_results = [
        {"candidate_id": cand_user["id"], "score": 0.91,
         "explanation": ["тест middle подтверждён → +0.33"]}
    ]
    return cand_headers, cand_user, emp_headers, emp_user


async def test_self_profile_has_contacts(client, fake_core):
    headers, user = await make_candidate(client)
    resp = await client.get("/api/v1/candidate/profile", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["phone"] == "+7 900 111-22-33"
    assert data["contacts"]["telegram"] == "@ivan"
    assert data["email"] == user["email"]


async def test_bank_hides_contacts_before_accept(client, fake_core):
    _, cand_user, emp_headers, _ = await _world(client, fake_core)
    resp = await client.get("/api/v1/employer/candidates", headers=emp_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    # ФИО и опыт видны (Q&A 07.10), скрыты только контакты
    assert item["profile"]["fio"] == "Иван Петров"
    assert item["profile"]["experience_years"] == 3
    assert item["profile"]["stack"] == ["python", "postgresql", "redis"]
    _assert_no_contacts(item, cand_user["email"])


async def test_shortlist_hides_contacts_before_accept(client, fake_core):
    _, cand_user, emp_headers, _ = await _world(client, fake_core)
    resp = await client.post(
        "/api/v1/employer/needs",
        json={"raw_text": "нужен backend middle python",
              "spec_slug": "backend", "grade": "middle",
              "stack_must": ["python"]},
        headers=emp_headers,
    )
    need_id = resp.json()["id"]
    resp = await client.get(
        f"/api/v1/employer/needs/{need_id}/shortlist", headers=emp_headers
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["explanation"]  # панель «Почему в подборке»
    _assert_no_contacts(results[0]["candidate"], cand_user["email"])


async def test_employer_tracker_hides_contacts_before_accept(
    client, fake_core
):
    _, cand_user, emp_headers, _ = await _world(client, fake_core)
    created = await make_invitation(client, emp_headers, cand_user["id"])
    _assert_no_contacts(created["candidate"], cand_user["email"])
    resp = await client.get(
        "/api/v1/employer/invitations", headers=emp_headers
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "sent"
    _assert_no_contacts(items[0]["candidate"], cand_user["email"])


async def test_candidate_sees_salary_but_not_company_contacts_before_accept(
    client, fake_core
):
    cand_headers, cand_user, emp_headers, _ = await _world(client, fake_core)
    await make_invitation(client, emp_headers, cand_user["id"])
    resp = await client.get(
        "/api/v1/candidate/invitations", headers=cand_headers
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    # вилка ЗП видна ДО ответа — принципиальное отличие (ТЗ §2.2.1)
    assert item["salary_from"] == 200000
    assert item["salary_to"] == 300000
    assert item["salary_type"] == "gross"
    assert item["company"]["company"]["name"] == "ООО Рога и копыта"
    assert item["company"]["contacts"] is None
    assert "hr@roga.dev" not in str(item)
    # первый просмотр: sent → viewed (§7.6)
    assert item["status"] == "viewed"


async def test_contacts_open_after_accept_both_ways(client, fake_core):
    """accept → кандидат видит контакты компании, работодатель —
    контакты кандидата в трекере И в банке."""
    cand_headers, cand_user, emp_headers, _ = await _world(client, fake_core)
    invitation = await make_invitation(
        client, emp_headers, cand_user["id"]
    )
    resp = await client.post(
        f"/api/v1/candidate/invitations/{invitation['id']}/accept",
        headers=cand_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["invitation"]
    # кандидату открылись контакты компании (зеркальное раскрытие §7.2)
    assert data["company"]["contacts"]["contacts"]["hr_email"] == (
        "hr@roga.dev"
    )
    # работодателю открылись контакты кандидата — в трекере
    resp = await client.get(
        "/api/v1/employer/invitations", headers=emp_headers
    )
    item = resp.json()[0]
    assert item["status"] == "accepted"
    contacts = item["candidate"]["contacts"]
    assert contacts is not None
    assert contacts["phone"] == "+7 900 111-22-33"
    assert contacts["contacts"]["telegram"] == "@ivan"
    assert contacts["email"] == cand_user["email"]
    # …и в банке кандидатов
    resp = await client.get("/api/v1/employer/candidates", headers=emp_headers)
    bank_contacts = resp.json()[0]["contacts"]
    assert bank_contacts is not None
    assert bank_contacts["email"] == cand_user["email"]


async def test_contacts_stay_hidden_for_other_employer(client, fake_core):
    """accept приглашения компании A не открывает контакты компании B."""
    cand_headers, cand_user, emp_a, _ = await _world(client, fake_core)
    emp_b, _ = await make_employer(client, name="Другая компания")
    invitation = await make_invitation(client, emp_a, cand_user["id"])
    await client.post(
        f"/api/v1/candidate/invitations/{invitation['id']}/accept",
        headers=cand_headers,
    )
    resp = await client.get("/api/v1/employer/candidates", headers=emp_b)
    _assert_no_contacts(resp.json()[0], cand_user["email"])


async def test_anonymous_mode_hides_fio(client, fake_core):
    """Анонимный режим «Кандидат #id» — опция кандидата (§7.2)."""
    await make_candidate(client, privacy={"anonymous": True})
    emp_headers, _ = await make_employer(client)
    resp = await client.get("/api/v1/employer/candidates", headers=emp_headers)
    item = resp.json()[0]
    assert item["profile"]["fio"].startswith("Кандидат #")
    assert "Иван" not in str(item)


async def test_privacy_show_stack_and_fsp(client, fake_core):
    await make_candidate(
        client, privacy={"show_stack": False, "show_fsp": False}
    )
    emp_headers, _ = await make_employer(client)
    resp = await client.get("/api/v1/employer/candidates", headers=emp_headers)
    profile = resp.json()[0]["profile"]
    assert profile["stack"] == []
    assert profile["fsp"] is None


async def test_candidate_cannot_read_bank(client, fake_core):
    cand_headers, _ = await make_candidate(client)
    resp = await client.get("/api/v1/employer/candidates", headers=cand_headers)
    assert resp.status_code == 403


async def test_candidate_cannot_accept_foreign_invitation(client, fake_core):
    _, cand_user, emp_headers, _ = await _world(client, fake_core)
    other_headers, _ = await make_candidate(client)
    invitation = await make_invitation(client, emp_headers, cand_user["id"])
    for verb in ("accept", "decline"):
        resp = await client.post(
            f"/api/v1/candidate/invitations/{invitation['id']}/{verb}",
            headers=other_headers,
        )
        assert resp.status_code == 404
