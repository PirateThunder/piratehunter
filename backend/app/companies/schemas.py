"""Схемы компании. Зеркально кандидатам: Public — без контактов,
Contacts — только после accept приглашения (§7.2)."""

from pydantic import BaseModel, Field


class CompanyIn(BaseModel):
    """PUT /employer/company — полная замена профиля компании."""

    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    industry: str | None = Field(default=None, max_length=200)
    contacts: dict = Field(default_factory=dict)
    site: str | None = Field(default=None, max_length=500)


class CompanyPublicOut(BaseModel):
    """Карточка компании для кандидата ДО accept: без contacts."""

    company_id: str
    name: str
    description: str | None
    industry: str | None
    site: str | None


class CompanyContactsOut(BaseModel):
    contacts: dict


class CompanyCandidateOut(BaseModel):
    """Компания в приглашении кандидата: contacts заполнены только
    после accept («контакты раскрываются обеим сторонам», §7.2)."""

    company: CompanyPublicOut
    contacts: CompanyContactsOut | None


class CompanySelfOut(BaseModel):
    """Свой профиль компании (GET /employer/company)."""

    company_id: str
    name: str
    description: str | None
    industry: str | None
    contacts: dict
    site: str | None
