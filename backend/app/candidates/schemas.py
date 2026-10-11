"""Схемы кандидата. Разделение Public/Contacts — уровень правил
видимости §7.6: контакты существуют только в Contacts-схеме, которую
собирает candidates/visibility.py и только при разрешении."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..constants import GRADES

SLUG_RE = r"^[a-z0-9][a-z0-9-]{0,63}$"


class PrivacyIn(BaseModel):
    """Настройки приватности (§7.2): анонимный режим — опция кандидата,
    не дефолт (Q&A 07.10: ФИО показывать допустимо, скрыты только
    контакты)."""

    anonymous: bool = False
    show_fsp: bool = True
    show_stack: bool = True


class ProfileIn(BaseModel):
    """PUT /candidate/profile — полная замена профиля (upsert)."""

    fio: str = Field(min_length=1, max_length=300)
    phone: str | None = Field(default=None, max_length=64)
    contacts: dict = Field(default_factory=dict)
    stack: list[str] = Field(default_factory=list, max_length=64)
    spec_slug: str | None = Field(default=None, pattern=SLUG_RE)
    grade_claimed: Literal[*GRADES] | None = None
    experience_years: int | None = Field(default=None, ge=0, le=60)
    roles: list[str] = Field(default_factory=list, max_length=32)
    soft_skills: list[str] = Field(default_factory=list, max_length=32)
    about: str | None = Field(default=None, max_length=10000)
    privacy: PrivacyIn = Field(default_factory=PrivacyIn)

    @field_validator("stack", "roles", "soft_skills")
    @classmethod
    def _strip_items(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s.strip()][:64]


class FspBlockOut(BaseModel):
    """Достижения ФСП в карточке: score + сырой документ реестра."""

    score: float
    achievements: dict


class CandidateContactsOut(BaseModel):
    """Контакты кандидата — отдельная схема, чтобы их нельзя было
    «случайно» отдать: собирается только visibility.to_contacts()."""

    email: str | None
    phone: str | None
    contacts: dict


class CandidatePublicOut(BaseModel):
    """Профиль БЕЗ контактов — то, что видит работодатель в банке и
    подборке (ФИО и опыт показываем — Q&A 07.10; неподтверждённый
    грейд — со статусом, §6)."""

    candidate_id: str
    fio: str  # «Кандидат #id» при privacy.anonymous
    spec_slug: str | None
    grade_claimed: str | None
    grade_verified: str | None
    grade_status: str  # unverified|confirmed|upgrade_offer|downgrade_offer
    experience_years: int | None
    stack: list[str]
    roles: list[str]
    soft_skills: list[str]
    about: str | None
    has_fsp: bool  # есть история ФСП (достижения подтянуты)
    fsp: FspBlockOut | None  # None — нет истории или privacy.show_fsp=0
    updated_at: datetime


class CandidateEmployerOut(BaseModel):
    """Карточка кандидата для работодателя: публичный профиль +
    contacts, заполненный ТОЛЬКО после accept приглашения (§7.6)."""

    profile: CandidatePublicOut
    contacts: CandidateContactsOut | None


class CandidateSelfOut(BaseModel):
    """Свой профиль целиком (GET /candidate/profile): публичная часть
    без анонимизации + контакты + приватность + ФСП-привязка."""

    candidate_id: str
    fio: str
    email: str | None
    phone: str | None
    contacts: dict
    spec_slug: str | None
    grade_claimed: str | None
    grade_verified: str | None
    grade_status: str
    experience_years: int | None
    stack: list[str]
    roles: list[str]
    soft_skills: list[str]
    about: str | None
    privacy: dict
    fsp_id: str | None
    has_fsp: bool
    fsp: FspBlockOut | None
    updated_at: datetime


class FspLinkIn(BaseModel):
    """POST /candidate/fsp-link: ручная привязка ФСП ID в настройках."""

    fsp_id: str = Field(min_length=1, max_length=64)


class GradeOut(BaseModel):
    """GET /candidate/grade: статус грейда, кулдауны, место в категории."""

    spec_slug: str | None
    grade_claimed: str | None
    grade_verified: str | None
    status: str
    theta: float | None
    last_test_at: datetime | None
    grade_changed_at: datetime | None
    # даты, когда доступны: повтор теста на текущий грейд / смена грейда
    retest_available_at: datetime | None
    change_available_at: datetime | None
    # место в ранжировании категории (core); None — нет подтверждённого
    # грейда или core недоступен
    category_rank: int | None
    category_size: int | None
