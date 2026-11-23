import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request

from app import storage
from app.routers.households import get_household_or_404
from app.schemas import InviteCreate, InviteRead, MemberRead, Phase

router = APIRouter(tags=["invites"])

INVITE_LIFETIME = timedelta(days=7)


@router.post("/households/{household_id}/invites", status_code=201)
def create_invite(household_id: int, body: InviteCreate, request: Request) -> InviteRead:
    household = get_household_or_404(household_id)
    if household.phase not in (Phase.SETUP, Phase.ACTIVE):
        raise HTTPException(status_code=409, detail="Cannot invite during estimation")

    token = secrets.token_urlsafe(32)
    invite = storage.Invite(
        id=storage.next_id(storage.invites),
        household_id=household_id,
        email=body.email,
        token=token,
        expires_at=datetime.now(timezone.utc) + INVITE_LIFETIME,
    )
    storage.invites[token] = invite

    # Until email sending exists (Layer 12), return the link instead of sending it.
    link = f"{request.base_url}invites/{token}/accept"
    return InviteRead(**invite.model_dump(), link=link)


@router.post("/invites/{token}/accept", status_code=201)
def accept_invite(token: str, x_user_name: str = Header()) -> MemberRead:
    invite = storage.invites.get(token)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=410, detail="Invite already used")
    now = datetime.now(timezone.utc)
    if now > invite.expires_at:
        raise HTTPException(status_code=410, detail="Invite expired")

    household = get_household_or_404(invite.household_id)
    if household.phase == Phase.ESTIMATION:
        raise HTTPException(status_code=409, detail="Cannot join during estimation")

    household_members = [
        m for m in storage.members.values() if m.household_id == household.id
    ]
    if any(m.email == invite.email for m in household_members):
        raise HTTPException(status_code=409, detail="Already a member")

    member_id = storage.next_id(storage.members)
    member = storage.Member(
        id=member_id,
        household_id=household.id,
        email=invite.email,
        display_name=x_user_name,
        turn_order=len(household_members) + 1,
        joined_at=now,
    )
    storage.members[member_id] = member
    invite.accepted_at = now
    return MemberRead(**member.model_dump())
