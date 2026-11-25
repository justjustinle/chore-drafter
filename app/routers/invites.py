import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import update
from sqlmodel import Session, select

from app.db import get_session
from app.models import Invite, Member, Phase, User, utc_now
from app.routers.households import get_household_or_404, get_or_create_user
from app.schemas import InviteCreate, InviteRead, MemberRead

router = APIRouter(tags=["invites"])

INVITE_LIFETIME = timedelta(days=7)


@router.post("/households/{household_id}/invites", status_code=201)
def create_invite(
    household_id: int,
    body: InviteCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> InviteRead:
    household = get_household_or_404(session, household_id)
    if household.phase not in (Phase.SETUP, Phase.ACTIVE):
        raise HTTPException(status_code=409, detail="Cannot invite during estimation")

    invite = Invite(
        household_id=household_id,
        email=body.email,
        token=secrets.token_urlsafe(32),
        expires_at=utc_now() + INVITE_LIFETIME,
    )
    session.add(invite)
    session.commit()

    # Until email sending exists (Layer 12), return the link instead of sending it.
    link = f"{request.base_url}invites/{invite.token}/accept"
    return InviteRead(
        id=invite.id,
        household_id=invite.household_id,
        email=invite.email,
        expires_at=invite.expires_at,
        link=link,
    )


@router.post("/invites/{token}/accept", status_code=201)
def accept_invite(
    token: str,
    x_user_name: str = Header(),
    session: Session = Depends(get_session),
) -> MemberRead:
    invite = session.exec(select(Invite).where(Invite.token == token)).first()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=410, detail="Invite already used")
    now = utc_now()
    if now > invite.expires_at:
        raise HTTPException(status_code=410, detail="Invite expired")

    household = get_household_or_404(session, invite.household_id)
    if household.phase == Phase.ESTIMATION:
        raise HTTPException(status_code=409, detail="Cannot join during estimation")

    user = get_or_create_user(session, invite.email, x_user_name)
    already_member = session.exec(
        select(Member).where(Member.household_id == household.id, Member.user_id == user.id)
    ).first()
    if already_member is not None:
        raise HTTPException(status_code=409, detail="Already a member")

    # Mark the invite used with a conditional update: it only succeeds if
    # accepted_at is still empty. If two requests race, the database lets
    # exactly one of them through; the other changes 0 rows and gets 410.
    result = session.execute(
        update(Invite)
        .where(Invite.id == invite.id, Invite.accepted_at.is_(None))
        .values(accepted_at=now)
    )
    if result.rowcount == 0:
        session.rollback()
        raise HTTPException(status_code=410, detail="Invite already used")

    member_count = len(
        session.exec(select(Member).where(Member.household_id == household.id)).all()
    )
    member = Member(
        household_id=household.id,
        user_id=user.id,
        display_name=x_user_name,
        turn_order=member_count + 1,
    )
    session.add(member)
    session.commit()
    return MemberRead(
        id=member.id,
        display_name=member.display_name,
        email=user.email,
        turn_order=member.turn_order,
        joined_at=member.joined_at,
    )
