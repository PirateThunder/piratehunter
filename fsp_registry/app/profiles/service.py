"""Детерминированный генератор синтетических профилей достижений.

Seed = sha256(соль + fsp_id): один и тот же fsp_id всегда даёт один и
тот же ответ, в том числе между перезапусками процесса. По хэшу ~60%
fsp_id имеют историю ФСП, ~40% → None (пользователь без истории —
обязательный кейс ТЗ, PRD §7.9).
"""

import hashlib
import random
from datetime import timedelta

from .constants import (
    CONTESTS,
    DATE_MAX,
    DATE_MIN,
    DISCIPLINES,
    EVENT_NAMES,
    EVENT_ROLES,
    HISTORY_SHARE,
    RANKS,
    RATING_MAX,
    RATING_MIN,
    SEED_SALT,
    TEAM_NAMES,
)
from .schemas import ContestEntry, EventEntry, FspProfile, RankEntry, TeamResult

_DATE_SPAN_DAYS = (DATE_MAX - DATE_MIN).days


def _rng_for(fsp_id: str) -> random.Random:
    digest = hashlib.sha256(f"{SEED_SALT}:{fsp_id}".encode()).hexdigest()
    return random.Random(int(digest, 16))


def _rand_date(rng: random.Random):
    return DATE_MIN + timedelta(days=rng.randint(0, _DATE_SPAN_DAYS))


def _make_contest(rng: random.Random) -> ContestEntry:
    name_template, discipline = rng.choice(CONTESTS)
    name = name_template.format(year=rng.randint(2021, 2026))
    # место: ~20% победители с дипломом I–III (диплом = месту),
    # ~25% призовые места 4–10, остальные — участники (11–60)
    roll = rng.random()
    if roll < 0.20:
        place = rng.randint(1, 3)
        diploma = place
    elif roll < 0.45:
        place = rng.randint(4, 10)
        diploma = None
    else:
        place = rng.randint(11, 60)
        diploma = None
    team = rng.random() < 0.35
    team_result = TeamResult(team_name=rng.choice(TEAM_NAMES), place=place) if team else None
    return ContestEntry(
        name=name,
        discipline=discipline,
        date=_rand_date(rng),
        place=place,
        diploma=diploma,
        team=team,
        team_result=team_result,
    )


def build_profile(fsp_id: str) -> FspProfile | None:
    """Профиль достижений по fsp_id или None, если истории ФСП нет."""
    rng = _rng_for(fsp_id)
    if rng.random() >= HISTORY_SHARE:
        return None

    contests = [_make_contest(rng) for _ in range(rng.randint(1, 7))]
    contests.sort(key=lambda c: c.date, reverse=True)

    disciplines: list[str] = rng.sample(DISCIPLINES, k=rng.randint(0, 3))
    ranks = [
        RankEntry(discipline=d, rank=rng.choice(RANKS), date=_rand_date(rng))
        for d in disciplines
    ]
    ranks.sort(key=lambda r: r.date)

    events = [
        EventEntry(
            name=rng.choice(EVENT_NAMES).format(year=rng.randint(2021, 2026)),
            date=_rand_date(rng),
            role=rng.choice(EVENT_ROLES),
        )
        for _ in range(rng.randint(0, 4))
    ]
    events.sort(key=lambda e: e.date, reverse=True)

    return FspProfile(
        fsp_id=fsp_id,
        rating=rng.randint(RATING_MIN, RATING_MAX),
        ranks=ranks,
        contests=contests,
        events=events,
    )
