"""Общие фикстуры: sqlite in-memory, FakeRedis, фейки core-api и
fsp_registry (dependency_overrides), тест-клиент. Ни одного реального
сетевого вызова."""

import itertools
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core_client.client import get_core_client
from app.database import get_db
from app.fsp.client import get_fsp_client
from app.main import app
from app.models import Base, import_models
from app.redis import get_redis

import_models()


class FakeRedis:
    """In-memory подмножество redis.asyncio (get/setex/incr/expire/
    delete — коды, лимиты, OIDC state, владельцы тест-сессий)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key):
        # как redis.asyncio: наружу bytes
        value = self.store.get(key)
        return value.encode() if isinstance(value, str) else value

    async def setex(self, key, _ttl, value):
        self.store[key] = value

    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key, 0)) + 1)
        return int(self.store[key])

    async def expire(self, key, _ttl):
        pass

    async def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


class FakeCoreClient:
    """Фейк core-api (контракт §8.2): каталог, старт/ответы сессий,
    снапшоты (записываются для проверок), match, ранжирование,
    LLM-парсинг потребности.

    answer_script — очередь ответов на POST answers; пустая → сразу
    результат confirmed на grade_target последнего старта.
    parse_result — ответ llm_parse_need; parse_error=True → CoreError
    (проверка best-effort путей)."""

    def __init__(
        self,
        *,
        match_results: list[dict] | None = None,
        ranking: list[dict] | None = None,
        parse_result: dict | None = None,
        parse_error: bool = False,
    ) -> None:
        self._counter = itertools.count(1)
        self.started: list[dict] = []
        self.answered: list[tuple[str, dict]] = []
        self.snapshots: list[tuple[str, dict]] = []
        self.answer_script: list[dict] = []
        self.match_results = match_results if match_results is not None else []
        self.ranking = ranking if ranking is not None else []
        self.last_grade_target: str = "middle"
        self.catalog_calls = 0
        self.parse_calls: list[str] = []
        self.parse_result = parse_result if parse_result is not None else {
            "spec": None, "grade": None, "stack_must": [],
            "stack_nice": [], "confidence": 0.0, "notes": "",
        }
        self.parse_error = parse_error
        self.parse_resume_calls: list[str] = []
        self.parse_resume_error = False
        self.parse_resume_result = {
            "spec": "backend", "grade_claimed": "middle",
            "stack": ["python", "fastapi", "postgresql"],
            "roles": ["backend-разработчик"], "experience_years": 3,
            "about": "Пишу API на FastAPI", "confidence": 0.8,
            "notes": "распознано",
        }
        self.snapshots_cleared = False

    async def get_catalog(self) -> dict:
        self.catalog_calls += 1
        return {
            "specializations": [{"slug": "backend", "title": "Backend"}],
            "grades": ["intern", "junior", "middle", "senior"],
        }

    async def start_session(
        self, candidate_id: str, spec: str, grade_target: str,
        mode: str = "full",
    ) -> dict:
        self.started.append(
            {"candidate_id": candidate_id, "spec": spec,
             "grade_target": grade_target, "mode": mode}
        )
        self.last_grade_target = grade_target
        session_id = f"ses-{next(self._counter)}"
        return {
            "session_id": session_id,
            "question": {"type": "mcq", "instance": {"text": "2+2?"},
                         "time_limit": 90},
        }

    async def answer(self, session_id: str, answer: dict) -> dict:
        self.answered.append((session_id, answer))
        if self.answer_script:
            return self.answer_script.pop(0)
        return {
            "result": {
                "theta": 1.2,
                "se": 0.3,
                "outcome": "confirmed",
                "grade_verified": self.last_grade_target,
                "breakdown": {"questions": 4},
            }
        }

    async def push_snapshot(self, candidate_id: str, snapshot: dict) -> None:
        self.snapshots.append((candidate_id, snapshot))

    async def match(self, need: dict) -> list[dict]:
        return list(self.match_results)

    async def llm_parse_need(self, raw_text: str) -> dict:
        self.parse_calls.append(raw_text)
        if self.parse_error:
            from app.core_client.client import CoreError

            raise CoreError("core-api недоступен")
        return dict(self.parse_result)

    async def parse_resume(self, text: str) -> dict:
        self.parse_resume_calls.append(text)
        if self.parse_resume_error:
            from app.core_client.client import CoreError

            raise CoreError("core-api недоступен")
        return dict(self.parse_resume_result)

    async def delete_snapshots(self) -> None:
        self.snapshots_cleared = True

    async def category_ranking(self, spec: str, grade: str) -> list[dict]:
        return list(self.ranking)


class FakeFspClient:
    """Фейк fsp_registry (контракт §8.3): мок-OIDC + реестр достижений.
    profiles=None → любой fsp_id даёт 404 («нет истории»)."""

    def __init__(
        self,
        *,
        profiles: dict[str, dict] | None = None,
        sub: str = "fsp-user-1",
    ) -> None:
        self.profiles = profiles
        self.sub = sub
        self.authorize_calls: list[tuple[str, str | None]] = []
        self.exchanged: list[str] = []

    def build_authorize_url(
        self, state: str, fsp_id: str | None = None
    ) -> str:
        self.authorize_calls.append((state, fsp_id))
        return f"http://fsp.test/oidc/authorize?state={state}"

    async def exchange_code(self, code: str) -> dict:
        self.exchanged.append(code)
        return {"access_token": "fsp-access-token"}

    async def userinfo(self, access_token: str) -> dict:
        return {"sub": self.sub}

    async def get_profile(self, fsp_id: str) -> dict | None:
        if self.profiles is None:
            return None
        return self.profiles.get(fsp_id)


@pytest.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def fake_redis():
    redis = FakeRedis()
    app.dependency_overrides[get_redis] = lambda: redis
    yield redis
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
def fake_core():
    core = FakeCoreClient()
    app.dependency_overrides[get_core_client] = lambda: core
    yield core
    app.dependency_overrides.pop(get_core_client, None)


@pytest.fixture
def fake_fsp():
    fsp = FakeFspClient()
    app.dependency_overrides[get_fsp_client] = lambda: fsp
    yield fsp
    app.dependency_overrides.pop(get_fsp_client, None)


@pytest.fixture(autouse=True)
def _reset_caches():
    # кэш каталога живёт в модуле между тестами
    import app.catalog as catalog_module

    catalog_module._cache = (0.0, None)
    yield
    catalog_module._cache = (0.0, None)


@pytest.fixture
async def client(
    session_factory, fake_redis, fake_core, fake_fsp
) -> AsyncGenerator[AsyncClient]:
    async def override_db() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def dev_login_on(monkeypatch):
    """Включает dev-login (BACK_AUTH_DEV_LOGIN=1)."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "auth_dev_login", True)


# --- хелперы сценариев ---

_emails = itertools.count(1)


async def register_via_email(
    client: AsyncClient, email: str | None = None
) -> tuple[dict[str, str], dict]:
    """Email-код (dev_code при BACK_ENV=local) → verify →
    (Bearer-заголовки, user)."""
    email = email or f"user-{next(_emails)}@test.dev"
    resp = await client.post(
        "/api/v1/auth/email/request", json={"email": email}
    )
    assert resp.status_code == 202, resp.text
    code = resp.json()["dev_code"]
    assert code, "dev_code обязателен при BACK_ENV=local без SMTP"
    resp = await client.post(
        "/api/v1/auth/email/verify", json={"email": email, "code": code}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


async def select_role(
    client: AsyncClient, headers: dict, role: str
) -> None:
    resp = await client.post(
        "/api/v1/users/me/role",
        json={"role": role, "consent_pd": True, "consent_publish": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


PROFILE_BODY = {
    "fio": "Иван Петров",
    "phone": "+7 900 111-22-33",
    "contacts": {"telegram": "@ivan", "github": "ivanpetrov"},
    "stack": ["python", "postgresql", "redis"],
    "spec_slug": "backend",
    "grade_claimed": "middle",
    "experience_years": 3,
    "roles": ["backend-разработчик"],
    "soft_skills": ["коммуникация"],
    "about": "Пишу API на FastAPI",
}

COMPANY_BODY = {
    "name": "ООО Рога и копыта",
    "description": "Делаем платформы",
    "industry": "IT",
    "contacts": {"hr_email": "hr@roga.dev", "telegram": "@roga_hr"},
    "site": "https://roga.dev",
}


async def make_candidate(
    client: AsyncClient, **profile_overrides
) -> tuple[dict, dict]:
    """Кандидат с заполненным профилем → (headers, user)."""
    headers, user = await register_via_email(client)
    await select_role(client, headers, "candidate")
    body = {**PROFILE_BODY, **profile_overrides}
    resp = await client.put(
        "/api/v1/candidate/profile", json=body, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return headers, user


async def make_employer(
    client: AsyncClient, **company_overrides
) -> tuple[dict, dict]:
    """Работодатель с профилем компании → (headers, user)."""
    headers, user = await register_via_email(client)
    await select_role(client, headers, "employer")
    body = {**COMPANY_BODY, **company_overrides}
    resp = await client.put(
        "/api/v1/employer/company", json=body, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return headers, user


async def make_invitation(
    client: AsyncClient,
    employer_headers: dict,
    candidate_id: str,
    **overrides,
) -> dict:
    body = {
        "candidate_id": candidate_id,
        "text": "Интересная позиция backend middle",
        "salary_from": 200000,
        "salary_to": 300000,
        "salary_type": "gross",
        "contact_method": "telegram",
        **overrides,
    }
    resp = await client.post(
        "/api/v1/employer/invitations", json=body,
        headers=employer_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
