"""Who is calling, and are they allowed?

Until auth (Layer 8) the caller is identified by the X-User-Email header.
Endpoints never read that header directly: they call these functions, so
Layer 8 can switch to API keys by changing only this file.
"""

from fastapi import Header, HTTPException
from sqlmodel import Session, select

from app.models import Household, Member, User


def get_caller_email(x_user_email: str = Header()) -> str:
    """FastAPI dependency: the caller's identity, taken from the request."""
    return x_user_email


def require_member(session: Session, household_id: int, caller_email: str) -> Member:
    """The caller's member row in this household, or 403."""
    member = session.exec(
        select(Member)
        .join(User, Member.user_id == User.id)
        .where(Member.household_id == household_id, User.email == caller_email)
    ).first()
    if member is None:
        raise HTTPException(status_code=403, detail="You are not a member of this household")
    return member


def require_owner(session: Session, household: Household, caller_email: str) -> Member:
    """The caller's member row, if they own the household, or 403."""
    member = require_member(session, household.id, caller_email)
    if member.id != household.owner_member_id:
        raise HTTPException(status_code=403, detail="Only the owner can do this")
    return member
