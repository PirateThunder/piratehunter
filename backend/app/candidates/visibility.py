"""Правила видимости профиля кандидата (PRD §7.6) — единая точка
сериализации. Роутеры НЕ ветвятся ad-hoc: они вызывают эти функции,
а решение «можно ли контакты» принимает invitations.service
(can_view_contacts).

Правила:
- работодателю — CandidateEmployerOut: публичный профиль (ФИО и опыт
  видны, Q&A 07.10) + contacts=None, пока нет accept'нутого приглашения
  от его компании (или отклика кандидата — фаза 2, вакансии);
- кандидату самому — CandidateSelfOut со всеми полями;
- privacy.anonymous — «Кандидат #id» вместо ФИО (опция кандидата §7.2);
- privacy.show_stack/show_fsp прячут стек/достижения из публичной
  карточки.
"""

from ..users.models import User
from .constants import DEFAULT_PRIVACY, GRADE_UNVERIFIED
from .models import CandidateProfile, GradeState
from .schemas import (
    CandidateContactsOut,
    CandidateEmployerOut,
    CandidatePublicOut,
    CandidateSelfOut,
    FspBlockOut,
)


def _privacy(profile: CandidateProfile) -> dict:
    return {**DEFAULT_PRIVACY, **(profile.privacy or {})}


def _grade_status(grade_state: GradeState | None) -> str:
    return grade_state.status if grade_state else GRADE_UNVERIFIED


def _fsp_block(profile: CandidateProfile) -> FspBlockOut | None:
    if profile.fsp_data is None:
        return None
    return FspBlockOut(score=profile.fsp_score, achievements=profile.fsp_data)


def to_public(
    profile: CandidateProfile, grade_state: GradeState | None = None
) -> CandidatePublicOut:
    """Публичная карточка: БЕЗ email/phone/contacts. Анонимизация и
    privacy-флаги применяются здесь и нигде больше."""
    privacy = _privacy(profile)
    fio = profile.fio
    if privacy["anonymous"]:
        fio = f"Кандидат #{profile.user_id[:8]}"
    return CandidatePublicOut(
        candidate_id=profile.user_id,
        fio=fio,
        spec_slug=profile.spec_slug,
        grade_claimed=profile.grade_claimed,
        grade_verified=grade_state.grade_verified if grade_state else None,
        grade_status=_grade_status(grade_state),
        experience_years=profile.experience_years,
        stack=list(profile.stack or []) if privacy["show_stack"] else [],
        roles=list(profile.roles or []),
        soft_skills=list(profile.soft_skills or []),
        about=profile.about,
        has_fsp=profile.fsp_data is not None,
        fsp=_fsp_block(profile) if privacy["show_fsp"] else None,
        updated_at=profile.updated_at,
    )


def to_contacts(profile: CandidateProfile, user: User) -> CandidateContactsOut:
    """Контакты кандидата. Вызывать ТОЛЬКО при contacts_allowed=True
    (invitations.service.can_view_contacts) или для самого кандидата."""
    return CandidateContactsOut(
        email=user.email, phone=profile.phone, contacts=profile.contacts or {}
    )


def to_employer_view(
    profile: CandidateProfile,
    user: User,
    grade_state: GradeState | None = None,
    *,
    contacts_allowed: bool,
) -> CandidateEmployerOut:
    """Карточка для работодателя. contacts открываются единственным
    способом — флагом contacts_allowed от правила §7.6."""
    return CandidateEmployerOut(
        profile=to_public(profile, grade_state),
        contacts=(
            to_contacts(profile, user) if contacts_allowed else None
        ),
    )


def to_self(
    profile: CandidateProfile,
    user: User,
    grade_state: GradeState | None = None,
) -> CandidateSelfOut:
    """Свой профиль: всё, без анонимизации."""
    return CandidateSelfOut(
        candidate_id=profile.user_id,
        fio=profile.fio,
        email=user.email,
        phone=profile.phone,
        contacts=profile.contacts or {},
        spec_slug=profile.spec_slug,
        grade_claimed=profile.grade_claimed,
        grade_verified=grade_state.grade_verified if grade_state else None,
        grade_status=_grade_status(grade_state),
        experience_years=profile.experience_years,
        stack=list(profile.stack or []),
        roles=list(profile.roles or []),
        soft_skills=list(profile.soft_skills or []),
        about=profile.about,
        privacy=_privacy(profile),
        fsp_id=user.fsp_id,
        has_fsp=profile.fsp_data is not None,
        fsp=_fsp_block(profile),
        updated_at=profile.updated_at,
    )
