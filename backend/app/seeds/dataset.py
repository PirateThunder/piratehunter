"""Детерминированная генерация датасета сидов (PRD §10).

Чистая функция: на вход — пул достижений ФСП {fsp_id: profile}
(детерминирован живым реестром), на выход — байт-в-байт одинаковый
датасет при одинаковом входе. Ни сети, ни wall-clock: id — uuid5 от
стабильных имён, rng — random.Random(SEED), время — фиксированная
база + rng-смещения.
"""

import hashlib
import json
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from ..fsp.scoring import compute_fsp_score
from .data import (
    ABOUT_TEMPLATES,
    COMPANY_INDUSTRIES,
    COMPANY_NAMES,
    CONTACT_METHODS,
    DEEP_PER_GRADE,
    DEEP_SPECS,
    FIRST_NAMES_F,
    FIRST_NAMES_M,
    GRADE_BANDS,
    GRADES,
    INVITATION_TEXTS,
    LAST_NAMES_F,
    LAST_NAMES_M,
    MARKET_SALARY,
    NEED_DEFS,
    SPEC_TITLES,
    STACK_POOLS,
    WIDE_PER_GRADE,
    WIDE_SPECS,
)

SEED = "piratehunter-v1"
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "piratehunter:seeds:v1")
BASE_TIME = datetime(2026, 10, 1, 12, 0, 0)

CANDIDATES_TOTAL = 300
FSP_SHARE = 0.6
VERIFIED_SHARE = 0.75
CONTRAST_PAIRS = 3  # пар «одинаковый стек, разный грейд» и столько же
# «сильная ФСП vs без неё» — итого 12 слотов в backend×middle

DEMO_CANDIDATE_EMAIL = "demo-candidate@ph.dev"
DEMO_CANDIDATE_FSP_EMAIL = "demo-candidate-fsp@ph.dev"
DEMO_EMPLOYER_EMAIL = "demo-employer@ph.dev"
DEMO_FSP_ID = "fsp_001"  # богатая история в сидах реестра


def uid(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))


def _theta_in_band(rng: random.Random, grade: str) -> float:
    """θ строго внутри полосы грейда (§6), сжатие к центру 15%..85%."""
    lo, hi = GRADE_BANDS[grade]
    span = hi - lo
    return round(lo + span * (0.15 + 0.7 * rng.random()), 3)


def _weighted_stack(rng: random.Random, spec: str) -> list[str]:
    pool = STACK_POOLS[spec]
    techs = [t for t, _ in pool]
    weights = [w for _, w in pool]
    count = rng.randint(3, 6)
    picked: list[str] = []
    while len(picked) < count:
        tech = rng.choices(techs, weights=weights, k=1)[0]
        if tech not in picked:
            picked.append(tech)
    return picked


def _experience(rng: random.Random, grade: str) -> int:
    """Слабая корреляция с грейдом (грейд ≠ стаж, §6)."""
    base = {"intern": 0.5, "junior": 1.5, "middle": 4.0, "senior": 8.0}[grade]
    return max(0, min(15, round(base + rng.gauss(0, 1.4))))


def _fio(rng: random.Random) -> str:
    if rng.random() < 0.55:
        return f"{rng.choice(LAST_NAMES_M)} {rng.choice(FIRST_NAMES_M)}"
    return f"{rng.choice(LAST_NAMES_F)} {rng.choice(FIRST_NAMES_F)}"


def _about(rng: random.Random, spec: str, stack: list[str], exp: int) -> str:
    template = rng.choice(ABOUT_TEMPLATES)
    title = SPEC_TITLES[spec]
    years = f"{exp} г." if exp < 5 else f"{exp} лет"
    return template.format(
        title=title,
        title_cap=title.capitalize(),
        title_dat=title + "ом" if not title.endswith("а") else title[:-1] + "ой",
        exp=years,
        stack=", ".join(stack[:4]),
        stack_main=stack[0],
    )


def _salary_in_band(
    rng: random.Random, spec: str, grade: str
) -> tuple[int, int]:
    lo, hi = MARKET_SALARY[spec][grade]

    def jitter(v: int) -> int:
        return int(round(v * rng.uniform(0.94, 1.06) / 5000) * 5000)

    return jitter(lo), jitter(hi)


@dataclass
class SeedDataset:
    """Весь эталонный датасет плоскими словарями (ORM-агностично)."""

    users: list[dict] = field(default_factory=list)
    profiles: list[dict] = field(default_factory=list)
    grade_states: list[dict] = field(default_factory=list)
    companies: list[dict] = field(default_factory=list)
    needs: list[dict] = field(default_factory=list)
    invitations: list[dict] = field(default_factory=list)

    def digest(self) -> str:
        """sha256 сериализованного датасета — метрика детерминизма."""
        payload = json.dumps(
            asdict(self), sort_keys=True, ensure_ascii=False, default=str
        )
        return hashlib.sha256(payload.encode()).hexdigest()


def _demo_users(ds: SeedDataset, fsp_profiles: dict[str, dict]) -> None:
    """Демо-аккаунты §10 — первыми, uuid5: dev-login попадёт в эти же
    строки (find_or_create по email)."""
    ds.users.append({
        "id": uid(f"user:{DEMO_CANDIDATE_EMAIL}"),
        "email": DEMO_CANDIDATE_EMAIL, "fsp_id": None, "role": "candidate",
        "is_verified": True, "consent_pd": True, "consent_publish": True,
        "created_at": BASE_TIME - timedelta(days=60),
    })
    ds.profiles.append({
        "user_id": uid(f"user:{DEMO_CANDIDATE_EMAIL}"),
        "fio": "Иван Демидов", "phone": "+7 900 000-00-01",
        "contacts": {"telegram": "@demo_candidate"},
        "stack": ["python", "fastapi", "postgresql", "redis", "docker"],
        "spec_slug": "backend", "grade_claimed": "middle",
        "experience_years": 3, "roles": ["backend-разработчик"],
        "soft_skills": ["коммуникация", "самостоятельность"],
        "about": "Демо-кандидат без истории ФСП (кейс §7.9). Пишу API "
        "на FastAPI, люблю тесты и чистые миграции.",
        "privacy": {"anonymous": False, "show_fsp": True,
                    "show_stack": True},
        "fsp_score": 0.0, "fsp_data": None,
        "updated_at": BASE_TIME - timedelta(days=1),
    })
    # без ФСП и без подтверждённого грейда — жюри может пройти его тест
    ds.grade_states.append({
        "candidate_id": uid(f"user:{DEMO_CANDIDATE_EMAIL}"),
        "grade_verified": None, "theta": None, "status": "unverified",
        "last_test_at": None, "grade_changed_at": None,
    })

    fsp_data = fsp_profiles.get(DEMO_FSP_ID)
    ds.users.append({
        "id": uid(f"user:{DEMO_CANDIDATE_FSP_EMAIL}"),
        "email": DEMO_CANDIDATE_FSP_EMAIL, "fsp_id": DEMO_FSP_ID,
        "role": "candidate",
        "is_verified": True, "consent_pd": True, "consent_publish": True,
        "created_at": BASE_TIME - timedelta(days=60),
    })
    ds.profiles.append({
        "user_id": uid(f"user:{DEMO_CANDIDATE_FSP_EMAIL}"),
        "fio": "Мария Спортсменова", "phone": "+7 900 000-00-02",
        "contacts": {"telegram": "@demo_candidate_fsp"},
        "stack": ["python", "fastapi", "postgresql", "redis", "docker",
                  "kubernetes"],
        "spec_slug": "backend", "grade_claimed": "middle",
        "experience_years": 4, "roles": ["backend-разработчик"],
        "soft_skills": ["лидерство", "менторство"],
        "about": "Демо-кандидат с историей ФСП: дипломы, разряды, "
        "командные результаты. Backend на FastAPI.",
        "privacy": {"anonymous": False, "show_fsp": True,
                    "show_stack": True},
        "fsp_score": compute_fsp_score(fsp_data),
        "fsp_data": fsp_data,
        "updated_at": BASE_TIME - timedelta(days=1),
    })
    ds.grade_states.append({
        "candidate_id": uid(f"user:{DEMO_CANDIDATE_FSP_EMAIL}"),
        "grade_verified": "middle", "theta": 1.21, "status": "confirmed",
        "last_test_at": BASE_TIME - timedelta(days=14),
        "grade_changed_at": BASE_TIME - timedelta(days=14),
    })

    ds.users.append({
        "id": uid(f"user:{DEMO_EMPLOYER_EMAIL}"),
        "email": DEMO_EMPLOYER_EMAIL, "fsp_id": None, "role": "employer",
        "is_verified": True, "consent_pd": True, "consent_publish": True,
        "created_at": BASE_TIME - timedelta(days=60),
    })
    ds.companies.append({
        "user_id": uid(f"user:{DEMO_EMPLOYER_EMAIL}"),
        "name": "Демо Корп",
        "description": "Демонстрационная компания платформы: показываем "
        "потребности, подборку и приглашения со статусами.",
        "industry": "IT-платформа",
        "contacts": {"hr_email": "hr@demo-corp.ph.dev",
                     "telegram": "@demo_corp_hr"},
        "site": "https://demo-corp.ph.dev",
    })


def _companies(ds: SeedDataset) -> list[str]:
    """15 компаний с employer-юзерами → [company_user_id, ...]."""
    company_ids = []
    for i in range(15):
        n = i + 1
        user_id = uid(f"user:seed-employer-{n:02d}")
        ds.users.append({
            "id": user_id,
            "email": f"seed-employer-{n:02d}@ph.dev", "fsp_id": None,
            "role": "employer", "is_verified": True,
            "consent_pd": True, "consent_publish": True,
            "created_at": BASE_TIME - timedelta(days=55),
        })
        name = COMPANY_NAMES[i]
        ds.companies.append({
            "user_id": user_id,
            "name": name,
            "description": f"{name} — продуктовая IT-компания. Развиваем "
            "свою платформу, ищем сильных инженеров.",
            "industry": COMPANY_INDUSTRIES[i % len(COMPANY_INDUSTRIES)],
            "contacts": {"hr_email": f"hr-{n:02d}@company.ph.dev",
                         "telegram": f"@hr_company_{n:02d}"},
            "site": f"https://company-{n:02d}.ph.dev",
        })
        company_ids.append(user_id)
    return company_ids


def _candidates(
    rng: random.Random, ds: SeedDataset, fsp_ids: list[str]
) -> list[dict]:
    """300 кандидатов квотной матрицей + контрастные слоты (§10).
    → [{idx, user_id, spec, grade_matrix, verified, fsp_id|None}] —
    план для приглашений/снапшотов."""
    slots: list[tuple[str, str]] = []  # (spec, matrix_grade)
    for spec in DEEP_SPECS:
        for grade in GRADES:
            slots.extend([(spec, grade)] * DEEP_PER_GRADE)
    for spec in WIDE_SPECS:
        for grade in GRADES:
            slots.extend([(spec, grade)] * WIDE_PER_GRADE)
    assert len(slots) == 288
    # контрастные слоты: 6 пар backend (§10)
    slots.extend([("backend", "middle")] * 12)

    # какие слоты получают ФСП (~60%): контрастные «сильная ФСП»
    # гарантированы, остальное — rng-выборка
    total = len(slots)
    guaranteed_fsp = {total - 12 + p * 2 for p in range(3, 6)}
    target = round(total * FSP_SHARE)
    rest = [i for i in range(total) if i not in guaranteed_fsp]
    rng.shuffle(rest)
    fsp_slots = guaranteed_fsp | set(rest[: target - len(guaranteed_fsp)])

    plan: list[dict] = []
    if len(fsp_ids) < target:
        raise ValueError(
            f"пул ФСП-профилей мал: {len(fsp_ids)} < {target} — "
            "наберите больше id из реестра"
        )
    for idx, (spec, matrix_grade) in enumerate(slots):
        n = idx + 1
        user_id = uid(f"user:seed-{n:03d}")
        verified = idx % 4 != 3  # ровно 75% verified
        contrast_pos = idx - (total - 12) if idx >= total - 12 else None

        stack = _weighted_stack(rng, spec)
        if contrast_pos is not None:
            # у пары одинаковый стек — вычисляем один раз на пару
            pair = contrast_pos // 2
            if contrast_pos % 2 == 0:
                stack = _weighted_stack(rng, spec)
                _contrast_stacks[pair] = stack
            else:
                stack = list(_contrast_stacks[pair])

        # грейд: контрастные слоты — все verified; пары 0..2 —
        # «одинаковый стек, разный грейд», пары 3..5 — «ФСП vs без неё»
        grade_verified = None
        theta = None
        status = "unverified"
        last_test_at = None
        grade_changed_at = None
        grade_claimed = matrix_grade
        if contrast_pos is not None:
            verified = True
            if contrast_pos < 6:
                grade_verified = (
                    "middle" if contrast_pos % 2 == 0 else "junior"
                )
            else:
                grade_verified = "middle"
            grade_claimed = grade_verified
        elif verified:
            grade_verified = matrix_grade
            # заявляемый обычно совпадает; иногда — на грейд выше/ниже
            roll = rng.random()
            g_idx = GRADES.index(matrix_grade)
            if roll < 0.15 and g_idx < len(GRADES) - 1:
                grade_claimed = GRADES[g_idx + 1]
            elif roll < 0.25 and g_idx > 0:
                grade_claimed = GRADES[g_idx - 1]

        if verified and grade_verified is not None:
            theta = _theta_in_band(rng, grade_verified)
            status = "confirmed"
            last_test_at = BASE_TIME - timedelta(
                days=rng.randint(7, 80), hours=rng.randint(0, 23)
            )
            grade_changed_at = last_test_at
        elif not verified and contrast_pos is None and rng.random() < 0.34:
            # unverified-ветка: θ есть, но грейд не подтверждён (§6)
            theta = _theta_in_band(rng, matrix_grade)
            status = "downgrade_offer"
            last_test_at = BASE_TIME - timedelta(days=rng.randint(7, 40))

        effective_grade = grade_verified or matrix_grade
        exp = _experience(rng, effective_grade)
        fsp_id = fsp_ids.pop(0) if idx in fsp_slots else None

        ds.users.append({
            "id": user_id,
            "email": f"seed-{n:03d}@candidates.ph.dev", "fsp_id": fsp_id,
            "role": "candidate", "is_verified": True,
            "consent_pd": True, "consent_publish": True,
            "created_at": BASE_TIME - timedelta(days=rng.randint(90, 300)),
        })
        fsp_data = _fsp_profiles.get(fsp_id) if fsp_id else None
        ds.profiles.append({
            "user_id": user_id,
            "fio": _fio(rng),
            "phone": f"+7 9{rng.randint(10, 99)} "
            f"{rng.randint(100, 999)}-{rng.randint(10, 99)}-"
            f"{rng.randint(10, 99)}",
            "contacts": {"telegram": f"@seed_{n:03d}",
                         "github": f"seed-{n:03d}"},
            "stack": stack,
            "spec_slug": spec, "grade_claimed": grade_claimed,
            "experience_years": exp,
            "roles": [SPEC_TITLES[spec]],
            "soft_skills": rng.sample(
                ["коммуникация", "самостоятельность", "работа в команде",
                 "ответственность", "наставничество", "аналитическое "
                 "мышление"], k=rng.randint(1, 3),
            ),
            "about": _about(rng, spec, stack, exp),
            "privacy": {"anonymous": False, "show_fsp": True,
                        "show_stack": True},
            "fsp_score": compute_fsp_score(fsp_data),
            "fsp_data": fsp_data,
            "updated_at": BASE_TIME - timedelta(days=rng.randint(0, 10)),
        })
        ds.grade_states.append({
            "candidate_id": user_id,
            "grade_verified": grade_verified, "theta": theta,
            "status": status,
            "last_test_at": last_test_at,
            "grade_changed_at": grade_changed_at,
        })
        plan.append({
            "idx": idx, "user_id": user_id, "spec": spec,
            "grade": effective_grade, "verified": verified,
        })
    return plan


# состояние между слотами контрастных пар (внутри одной генерации)
_contrast_stacks: dict[int, list[str]] = {}
_fsp_profiles: dict[str, dict] = {}


def _needs(rng: random.Random, ds: SeedDataset,
           company_ids: list[str]) -> None:
    demo_company = uid(f"user:{DEMO_EMPLOYER_EMAIL}")
    for i, spec_def in enumerate(NEED_DEFS):
        owner = spec_def["company"]
        company_id = demo_company if owner == "demo" else company_ids[owner]
        salary_from, salary_to = _salary_in_band(
            rng, spec_def["spec"], spec_def["grade"]
        )
        ds.needs.append({
            "id": uid(f"need:{i}"),
            "company_id": company_id,
            "raw_text": spec_def["raw_text"],
            "parsed": None,
            "stack_must": list(spec_def["stack_must"]),
            "stack_nice": list(spec_def["stack_nice"]),
            "spec_slug": spec_def["spec"], "grade": spec_def["grade"],
            "salary_from": salary_from, "salary_to": salary_to,
            "created_at": BASE_TIME - timedelta(days=rng.randint(3, 20)),
        })


def _invitations(
    rng: random.Random, ds: SeedDataset, company_ids: list[str],
    plan: list[dict],
) -> None:
    """~40 приглашений: pending демо-кандидату (сочная вилка — хук
    §7.11.3), трекер демо-работодателя, accepted для рынка вилок."""
    demo_company = uid(f"user:{DEMO_EMPLOYER_EMAIL}")
    demo_fsp_candidate = uid(f"user:{DEMO_CANDIDATE_FSP_EMAIL}")
    verified = [p for p in plan if p["verified"]]
    v_idx = 0

    def next_verified() -> dict:
        nonlocal v_idx
        plan_row = verified[v_idx % len(verified)]
        v_idx += 1
        return plan_row

    seq = 0

    def add(company_id: str, candidate_id: str, spec: str, grade: str,
            status: str, salary_from: int, salary_to: int) -> None:
        nonlocal seq
        created = BASE_TIME - timedelta(days=rng.randint(0, 20))
        if status == "sent":
            status_at = created
        else:
            status_at = created + timedelta(days=rng.randint(1, 5))
        ds.invitations.append({
            "id": uid(f"invitation:{seq}"),
            "company_id": company_id, "candidate_id": candidate_id,
            "text": INVITATION_TEXTS[seq % len(INVITATION_TEXTS)].format(
                spec=SPEC_TITLES[spec]
            ),
            "salary_from": salary_from, "salary_to": salary_to,
            "salary_type": "gross" if seq % 5 else "net",
            "contact_method": CONTACT_METHODS[seq % len(CONTACT_METHODS)],
            "status": status,
            "created_at": created, "status_at": status_at,
        })
        seq += 1

    # 1) 2 pending (sent) демо-кандидату с ФСП — сочная вилка (выше
    # медианы его категории, §7.11.3)
    add(company_ids[4], demo_fsp_candidate, "backend", "middle", "sent",
        400_000, 550_000)
    add(company_ids[6], demo_fsp_candidate, "backend", "middle", "sent",
        380_000, 520_000)

    # 2) 8 от демо-работодателя в разных статусах (трекер §7.3)
    for status in ("sent", "sent", "viewed", "viewed",
                   "accepted", "accepted", "declined", "declined"):
        row = next_verified()
        f, t = _salary_in_band(rng, row["spec"], row["grade"])
        add(demo_company, row["user_id"], row["spec"], row["grade"],
            status, f, t)

    # 3) 12 accepted сид-компаний → сид-кандидатам (рынок вилок §7.5.5)
    for i in range(12):
        row = next_verified()
        f, t = _salary_in_band(rng, row["spec"], row["grade"])
        add(company_ids[i % len(company_ids)], row["user_id"],
            row["spec"], row["grade"], "accepted", f, t)

    # 4) остаток — микс sent/viewed/declined
    for i in range(18):
        row = next_verified()
        f, t = _salary_in_band(rng, row["spec"], row["grade"])
        status = ("sent", "viewed", "declined")[i % 3]
        add(rng.choice(company_ids), row["user_id"],
            row["spec"], row["grade"], status, f, t)


def generate(fsp_profiles: dict[str, dict]) -> SeedDataset:
    """Сгенерировать эталонный датасет. fsp_profiles — пул достижений
    {fsp_id: profile} (детерминирован реестром; должен включать
    DEMO_FSP_ID и достаточный пул для ~60% кандидатов)."""
    global _contrast_stacks, _fsp_profiles
    _contrast_stacks = {}
    _fsp_profiles = dict(fsp_profiles)
    rng = random.Random(SEED)
    ds = SeedDataset()
    _demo_users(ds, fsp_profiles)
    company_ids = _companies(ds)
    fsp_ids = [k for k in fsp_profiles if k != DEMO_FSP_ID]
    plan = _candidates(rng, ds, fsp_ids)
    _needs(rng, ds, company_ids)
    _invitations(rng, ds, company_ids, plan)
    return ds
