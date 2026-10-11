"""Ручки приглашений: исходящие у работодателя, входящие у кандидата.

Видимость контактов — только через invitations.service (accept от
компании) + сериализаторы visibility (никаких ad-hoc if в роутерах).
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..auth.dependencies import CandidateUser, EmployerUser
from ..candidates import visibility
from ..candidates.models import CandidateProfile, GradeState
from ..companies import service as companies_service
from ..database import DbDep
from ..redis import RedisDep
from ..users.models import User
from . import service
from .constants import ACCEPTED
from .models import Invitation
from .schemas import (
    InvitationAcceptOut,
    InvitationBaseOut,
    InvitationCandidateOut,
    InvitationCreateIn,
    InvitationEmployerOut,
)

router = APIRouter(tags=["invitations"])


def _candidate_card(
    invitation: Invitation, companies: dict
) -> InvitationCandidateOut:
    """Входящее кандидата: вилка ЗП видна ДО ответа (ТЗ §2.2.1);
    контакты компании — только после accept (§7.2)."""
    company = companies.get(invitation.company_id)
    if company is None:
        raise HTTPException(500, "компания приглашения не найдена")
    return InvitationCandidateOut(
        **InvitationBaseOut.model_validate(invitation).model_dump(),
        company=companies_service.to_candidate_view(
            company, contacts_allowed=invitation.status == ACCEPTED
        ),
    )


# --- работодатель ---


@router.post(
    "/employer/invitations",
    response_model=InvitationEmployerOut,
    status_code=201,
    summary="Отправить приглашение кандидату",
)
async def create_invitation(
    body: InvitationCreateIn,
    user: EmployerUser,
    session: DbDep,
    redis: RedisDep,
) -> InvitationEmployerOut:
    """Текст + обязательная вилка ЗП (gross|net) + способ связи.
    Лимит создания в час (NFR §12)."""
    await companies_service.get_company_or_404(session, user.id)
    invitation = await service.create(session, redis, user.id, body)
    profile = await session.get(CandidateProfile, body.candidate_id)
    candidate = await session.get(User, body.candidate_id)
    grade_state = await session.get(GradeState, body.candidate_id)
    return InvitationEmployerOut(
        **InvitationBaseOut.model_validate(invitation).model_dump(),
        candidate=visibility.to_employer_view(
            profile, candidate, grade_state, contacts_allowed=False
        ),
    )


@router.get(
    "/employer/invitations",
    response_model=list[InvitationEmployerOut],
    summary="Мои приглашения (трекер статусов)",
)
async def list_invitations(
    user: EmployerUser, session: DbDep
) -> list[InvitationEmployerOut]:
    """Трекер: отправлено/просмотрено/принято/отклонено. Контакты
    кандидата раскрыты в строках со статусом accepted (§7.6)."""
    invitations = await service.list_for_employer(session, user.id)
    candidate_ids = [i.candidate_id for i in invitations]
    profiles = {
        p.user_id: p
        for p in await session.scalars(
            select(CandidateProfile).where(
                CandidateProfile.user_id.in_(candidate_ids)
            )
        )
    }
    users = {
        u.id: u
        for u in await session.scalars(
            select(User).where(User.id.in_(candidate_ids))
        )
    }
    grade_states = {
        g.candidate_id: g
        for g in await session.scalars(
            select(GradeState).where(GradeState.candidate_id.in_(candidate_ids))
        )
    }
    allowed = await service.contacts_allowed_ids(
        session, user.id, candidate_ids
    )
    out = []
    for invitation in invitations:
        cid = invitation.candidate_id
        profile, candidate = profiles.get(cid), users.get(cid)
        if profile is None or candidate is None:
            continue
        out.append(
            InvitationEmployerOut(
                **InvitationBaseOut.model_validate(invitation).model_dump(),
                candidate=visibility.to_employer_view(
                    profile,
                    candidate,
                    grade_states.get(cid),
                    contacts_allowed=cid in allowed,
                ),
            )
        )
    return out


# --- кандидат ---


@router.get(
    "/candidate/invitations",
    response_model=list[InvitationCandidateOut],
    summary="Входящие приглашения",
)
async def list_incoming(
    user: CandidateUser, session: DbDep
) -> list[InvitationCandidateOut]:
    """Входящие: компания, текст, вилка ЗП, способ связи — всё видно
    ДО ответа. Первый просмотр переводит sent → viewed (§7.6)."""
    invitations = await service.list_for_candidate(session, user.id)
    companies = await service.load_companies(
        session, [i.company_id for i in invitations]
    )
    return [_candidate_card(i, companies) for i in invitations]


@router.post(
    "/candidate/invitations/{invitation_id}/accept",
    response_model=InvitationAcceptOut,
    summary="Принять приглашение",
)
async def accept_invitation(
    invitation_id: str, user: CandidateUser, session: DbDep
) -> InvitationAcceptOut:
    """Accept → контакты раскрываются ОБЕИМ сторонам: кандидат видит
    контакты компании, компания — контакты кандидата (§7.2, §7.6)."""
    invitation = await service.accept(session, user.id, invitation_id)
    companies = await service.load_companies(
        session, [invitation.company_id]
    )
    return InvitationAcceptOut(
        invitation=_candidate_card(invitation, companies)
    )


@router.post(
    "/candidate/invitations/{invitation_id}/decline",
    response_model=InvitationCandidateOut,
    summary="Отклонить приглашение",
)
async def decline_invitation(
    invitation_id: str, user: CandidateUser, session: DbDep
) -> InvitationCandidateOut:
    invitation = await service.decline(session, user.id, invitation_id)
    companies = await service.load_companies(
        session, [invitation.company_id]
    )
    return _candidate_card(invitation, companies)
