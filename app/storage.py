"""In-memory storage. Everything is lost when the server stops.

Each record class below becomes a database table in Layer 2.
"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas import Phase


class Household(BaseModel):
    id: int
    name: str
    phase: Phase
    owner_member_id: int
    created_at: datetime


class Member(BaseModel):
    id: int
    household_id: int
    email: str
    display_name: str
    turn_order: int
    joined_at: datetime


class Invite(BaseModel):
    id: int
    household_id: int
    email: str
    token: str
    expires_at: datetime
    accepted_at: datetime | None = None


class Chore(BaseModel):
    id: int
    household_id: int
    name: str
    description: str | None
    effort_points: int | None = None
    created_by: int


# Each dict maps an id (or a token) to a record.
households: dict[int, Household] = {}
members: dict[int, Member] = {}
invites: dict[str, Invite] = {}  # keyed by token, so lookups by token are quick
chores: dict[int, Chore] = {}


def next_id(table: dict) -> int:
    return len(table) + 1


def reset() -> None:
    """Empty every table. Tests call this before each test."""
    households.clear()
    members.clear()
    invites.clear()
    chores.clear()
