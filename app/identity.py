"""Who is calling, and are they allowed? (Layer 8: API keys.)

Every member gets an API key when they create a household or accept an
invite. The key is shown once; the database stores only its SHA-256 hash,
so a leaked database does not leak working keys. Each request sends the key
in the X-API-Key header, and the key decides who the caller is: nobody can
act as someone else by changing an email header any more.

A plain SHA-256 is enough here (passwords would need a slow hash like
bcrypt): the keys are 32 random bytes, far too many to guess, and a fast,
repeatable hash lets us look a key up directly.
"""

import hashlib
import secrets

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Household, Member


def new_api_key() -> tuple[str, str]:
    """A fresh key and its hash. Give the key to the member; store the hash."""
    key = "cd_" + secrets.token_urlsafe(32)
    return key, hash_key(key)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_caller(
    x_api_key: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Member:
    """FastAPI dependency: the member whose key was sent, or 401."""
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Send your API key in the X-API-Key header")
    member = session.exec(select(Member).where(Member.api_key_hash == hash_key(x_api_key))).first()
    if member is None:
        raise HTTPException(status_code=401, detail="Unknown API key")
    return member


def require_member(session: Session, household_id: int, caller: Member) -> Member:
    """The caller, if they belong to this household, or 403.

    A key belongs to one membership, so a member of household A using their
    key on household B is refused even if they are also a member of B
    (they must use B's key).
    """
    if caller.household_id != household_id:
        raise HTTPException(status_code=403, detail="You are not a member of this household")
    return caller


def require_owner(session: Session, household: Household, caller: Member) -> Member:
    """The caller, if they own the household, or 403."""
    member = require_member(session, household.id, caller)
    if member.id != household.owner_member_id:
        raise HTTPException(status_code=403, detail="Only the owner can do this")
    return member
