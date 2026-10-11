"""Модель FspProfile — по PRD §5.3 (состав подтверждён Q&A 06.10)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TeamResult(BaseModel):
    team_name: str
    place: int = Field(ge=1)


class ContestEntry(BaseModel):
    name: str
    discipline: str
    date: date
    place: int = Field(ge=1)
    diploma: Literal[1, 2, 3] | None  # диплом I/II/III степени (места 1–3)
    team: bool
    team_result: TeamResult | None


class RankEntry(BaseModel):
    discipline: str
    rank: str
    date: date


class EventEntry(BaseModel):
    name: str
    date: date
    role: str


class FspProfile(BaseModel):
    """Реестр достижений участника ФСП. ПДн нет — привязка к кандидату
    живёт в backend (PRD §4.2). Поле level у соревнований не заводим:
    эксперты против ранжирования дисциплин и уровней (PRD §7.9)."""

    fsp_id: str
    rating: int
    ranks: list[RankEntry]
    contests: list[ContestEntry]
    events: list[EventEntry]
