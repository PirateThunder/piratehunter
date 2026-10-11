"""Резюме (§7.10): обезличивание текста, POST /candidate/profile/resume
(multipart → draft; 422; core down → пустой draft), PDF-профиль."""

import pytest

from app.resume.sanitize import sanitize_resume_text
from tests.conftest import make_candidate


def make_pdf(text: str) -> bytes:
    """Минимальный валидный PDF 1.4 с одной текстовой строкой
    (latin-1) — для прогона реального пути pypdf в тестах."""
    content_stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode(
        "latin-1"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content_stream)).encode()
        + b" >>\nstream\n" + content_stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode()
    return bytes(out)


RESUME_TEXT = (
    "Python FastAPI backend, 3 years. ivan@test.dev +7 900 111-22-33 "
    "@ivan_hr https://linkedin.com/in/ivan"
)


def test_sanitize_strips_contacts():
    clean = sanitize_resume_text(
        "Иван Петров, ivan.petrov@mail.ru, +7 (926) 123-45-67, "
        "8 926 123 45 67, @ivan_petrov, https://github.com/ivan, "
        "www.ivan.dev — backend разработчик"
    )
    assert "ivan.petrov@mail.ru" not in clean
    assert "926" not in clean.replace("[телефон]", "")
    assert "@ivan_petrov" not in clean
    assert "github.com" not in clean
    assert "www.ivan.dev" not in clean
    assert "[email]" in clean and "[телефон]" in clean
    assert "[контакт]" in clean and "[ссылка]" in clean
    # профессиональный текст не пострадал
    assert "backend разработчик" in clean


def test_sanitize_keeps_plain_text():
    text = "Python, FastAPI, PostgreSQL. 5 лет опыта."
    assert sanitize_resume_text(text) == text


async def test_resume_upload_returns_draft(client, fake_core):
    headers, _ = await make_candidate(client)
    resp = await client.post(
        "/api/v1/candidate/profile/resume",
        files={"file": ("resume.pdf", make_pdf(RESUME_TEXT),
                        "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    draft = resp.json()["draft"]
    assert draft["spec"] == "backend"
    assert draft["grade_claimed"] == "middle"
    assert draft["stack"] == ["python", "fastapi", "postgresql"]
    assert draft["confidence"] == 0.8
    # в core ушёл ОБЕЗЛИЧЕННЫЙ текст (privacy by design, §3.4)
    sent = fake_core.parse_resume_calls[-1]
    assert "ivan@test.dev" not in sent
    assert "+7 900" not in sent
    assert "@ivan_hr" not in sent
    assert "linkedin.com" not in sent
    assert "FastAPI" in sent  # профессиональная часть на месте


async def test_resume_upload_not_pdf_422(client):
    headers, _ = await make_candidate(client)
    resp = await client.post(
        "/api/v1/candidate/profile/resume",
        files={"file": ("resume.pdf", b"not a pdf at all",
                        "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "PDF" in resp.json()["detail"]


async def test_resume_upload_core_down_empty_draft(client, fake_core):
    fake_core.parse_resume_error = True
    headers, _ = await make_candidate(client)
    resp = await client.post(
        "/api/v1/candidate/profile/resume",
        files={"file": ("resume.pdf", make_pdf(RESUME_TEXT),
                        "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    draft = resp.json()["draft"]
    assert draft["spec"] is None
    assert draft["stack"] == []
    assert "недоступен" in draft["notes"]


async def test_resume_upload_requires_candidate_role(client):
    from tests.conftest import make_employer

    emp_headers, _ = await make_employer(client)
    resp = await client.post(
        "/api/v1/candidate/profile/resume",
        files={"file": ("resume.pdf", make_pdf(RESUME_TEXT),
                        "application/pdf")},
        headers=emp_headers,
    )
    assert resp.status_code == 403


async def test_profile_pdf_endpoint(client, fake_core):
    """weasyprint работает headless в тестовом окружении (pango на
    хосте есть) — проверяем реальный рендер."""
    headers, _ = await make_candidate(client)
    resp = await client.get("/api/v1/candidate/profile/pdf",
                            headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert len(resp.content) > 1000


async def test_profile_pdf_no_contacts_inside(client, fake_core):
    """PDF публичен: ни email, ни телефона в байтах документа."""
    headers, user = await make_candidate(client)
    resp = await client.get("/api/v1/candidate/profile/pdf",
                            headers=headers)
    assert resp.status_code == 200
    body = resp.content
    # контакты не должны встречаться в открытом виде в потоке PDF
    assert user["email"].encode() not in body
    assert b"+7 900 111-22-33" not in body
    assert b"@ivan" not in body


@pytest.mark.parametrize("path", ["/api/v1/candidate/profile/resume"])
async def test_resume_requires_auth(client, path):
    resp = await client.post(
        path,
        files={"file": ("resume.pdf", make_pdf(RESUME_TEXT),
                        "application/pdf")},
    )
    assert resp.status_code == 401
