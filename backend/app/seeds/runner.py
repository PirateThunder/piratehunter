"""Раннер сидов (PRD §10): ресед базы к эталонному состоянию.

Запуск: python -m app.seeds (только BACK_ENV=local!).

Порядок: предохранитель env → пул ФСП-профилей из ЖИВОГО реестра
(детерминированные fsp-seed-NNNN) → генерация датасета (uuid5, rng
фиксирован) → truncate доменных таблиц + DELETE /internal/snapshots →
заливка → пуш снапшотов → проверка backend×middle ≥ 10 → сводка.
Повторный прогон даёт то же состояние (id детерминированы).
"""

import asyncio
import logging
import sys

from sqlalchemy import select, text

from ..candidates.models import CandidateProfile, GradeState
from ..candidates.service import build_snapshot
from ..companies.models import Company
from ..config import get_settings
from ..core_client.client import CoreClient, CoreError
from ..database import SessionFactory
from ..fsp.client import FspClient
from ..invitations.models import Invitation
from ..needs.models import Need
from ..users.models import User
from .dataset import (
    CANDIDATES_TOTAL,
    DEMO_FSP_ID,
    FSP_SHARE,
    SeedDataset,
    generate,
)

logger = logging.getLogger(__name__)

FSP_ID_PREFIX = "fsp-seed-"
FSP_PROBE_LIMIT = 2000

TRUNCATE_SQL = text(
    'TRUNCATE invitation, need, company, grade_state, '
    'candidate_profile, "user" RESTART IDENTITY CASCADE'
)


async def probe_fsp_pool(
    fsp: FspClient, needed: int
) -> dict[str, dict]:
    """Пул id, дающих 200 в живом реестре: fsp-seed-0001, 0002, …
    Реестр детерминирован → пул и его порядок стабильны между
    реседами. 404 = «нет истории» — пропускаем."""
    pool: dict[str, dict] = {}
    i = 0
    while len(pool) < needed and i < FSP_PROBE_LIMIT:
        batch = range(i + 1, i + 21)
        profiles = await asyncio.gather(
            *(fsp.get_profile(f"{FSP_ID_PREFIX}{n:04d}") for n in batch)
        )
        for n, profile in zip(batch, profiles, strict=True):
            if profile is not None:
                pool[f"{FSP_ID_PREFIX}{n:04d}"] = profile
        i = batch.stop
    if len(pool) < needed:
        raise SystemExit(
            f"ошибка сида: в реестре набралось только {len(pool)} "
            f"{FSP_ID_PREFIX}* профилей из {needed} нужных "
            f"(проверено {FSP_ID_PREFIX}0001..{i:04d})"
        )
    # отсекаем ровно needed первых по порядку id — стабильный пул
    return dict(sorted(pool.items())[:needed])


async def _insert_all(session, ds: SeedDataset) -> None:
    """Заливка в порядке FK-зависимостей (без ORM- relationships
    юнит оф ворк порядок таблиц не выводит — флашим явно)."""
    session.add_all(User(**row) for row in ds.users)
    await session.flush()
    session.add_all(CandidateProfile(**row) for row in ds.profiles)
    session.add_all(GradeState(**row) for row in ds.grade_states)
    session.add_all(Company(**row) for row in ds.companies)
    await session.flush()
    session.add_all(Need(**row) for row in ds.needs)
    session.add_all(Invitation(**row) for row in ds.invitations)
    await session.flush()


async def _push_snapshots(core: CoreClient) -> int:
    """Снапшоты всем кандидатам (контракт §4.3) — после заливки,
    форма строго как у боевого build_snapshot."""
    sem = asyncio.Semaphore(16)
    async with SessionFactory() as session:
        rows = (
            await session.execute(
                select(CandidateProfile, GradeState).outerjoin(
                    GradeState,
                    GradeState.candidate_id == CandidateProfile.user_id,
                )
            )
        ).all()

    async def push(profile: CandidateProfile, gs: GradeState | None) -> None:
        async with sem:
            await core.push_snapshot(
                profile.user_id, build_snapshot(profile, gs)
            )

    await asyncio.gather(*(push(p, g) for p, g in rows))
    return len(rows)


async def main() -> None:
    settings = get_settings()
    if settings.env != "local":
        raise SystemExit(
            f"отказ: сиды только при BACK_ENV=local (сейчас {settings.env})"
        )
    logging.basicConfig(level=logging.WARNING)
    core = CoreClient()
    fsp = FspClient()

    needed = round(CANDIDATES_TOTAL * FSP_SHARE)
    print(f"пул ФСП: набираю {needed} профилей {FSP_ID_PREFIX}* из "
          f"живого реестра…")
    fsp_profiles = await probe_fsp_pool(fsp, needed)
    demo_profile = await fsp.get_profile(DEMO_FSP_ID)
    if demo_profile is None:
        raise SystemExit(
            f"ошибка сида: в реестре нет демо-профиля {DEMO_FSP_ID}"
        )
    fsp_profiles[DEMO_FSP_ID] = demo_profile
    print(f"пул ФСП: {needed} + демо {DEMO_FSP_ID} — ок")

    ds = generate(fsp_profiles)
    print(f"датасет сгенерирован (digest {ds.digest()[:12]}…): "
          f"{len(ds.users)} users, {len(ds.profiles)} профилей, "
          f"{len(ds.companies)} компаний, {len(ds.needs)} потребностей, "
          f"{len(ds.invitations)} приглашений")

    print("truncate доменных таблиц + заливка…")
    async with SessionFactory() as session:
        await session.execute(TRUNCATE_SQL)
        await _insert_all(session, ds)
        await session.commit()

    try:
        await core.delete_snapshots()
        print("core: снапшоты очищены (DELETE /internal/snapshots)")
    except CoreError as e:
        # контракт фазы 3; до его выкатки (404) ресед не блокируем —
        # детерминированные id перезапишутся PUT'ами
        print(f"core: очистка снапшотов недоступна ({e}) — продолжаю, "
              "PUT'ы перезапишут", file=sys.stderr)

    pushed = await _push_snapshots(core)
    print(f"core: запушено снапшотов: {pushed}")

    # приёмка сида: категория backend×middle непустая (§10)
    ranking = await core.category_ranking("backend", "middle")
    if len(ranking) < 10:
        raise SystemExit(
            f"ошибка сида: backend×middle в core ranking — {len(ranking)}, "
            "ожидалось ≥ 10"
        )

    verified = sum(
        1 for g in ds.grade_states if g["grade_verified"] is not None
    )
    with_fsp = sum(1 for p in ds.profiles if p["fsp_data"] is not None)
    print("\n=== Ресед завершён ===")
    print(f"кандидатов:        {len(ds.profiles)} "
          f"(verified {verified}, с ФСП {with_fsp})")
    print(f"компаний:          {len(ds.companies)}")
    print(f"потребностей:      {len(ds.needs)}")
    print(f"приглашений:       {len(ds.invitations)}")
    print("категории в core (backend × грейд):")
    for grade in ("intern", "junior", "middle", "senior"):
        size = len(await core.category_ranking("backend", grade))
        print(f"  backend × {grade:<7} {size}")
    await core.close()
    await fsp.close()


if __name__ == "__main__":
    asyncio.run(main())
