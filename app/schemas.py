"""The shapes of data going in and out of the API.

*Create models are what the client sends.
*Read models are what the server sends back.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


class Phase(StrEnum):
    SETUP = "SETUP"
    ESTIMATION = "ESTIMATION"
    ACTIVE = "ACTIVE"


# ---------- Households ----------

class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class MemberRead(BaseModel):
    id: int
    display_name: str
    email: str
    turn_order: int
    joined_at: datetime


class ChoreRead(BaseModel):
    id: int
    household_id: int
    name: str
    description: str | None
    effort_points: int | None
    created_by: int
    colour: str | None = None


class HouseholdRead(BaseModel):
    id: int
    name: str
    phase: Phase
    owner_member_id: int
    created_at: datetime
    members: list[MemberRead]
    chores: list[ChoreRead]


# ---------- Invites ----------

class InviteCreate(BaseModel):
    email: EmailStr


class InviteRead(BaseModel):
    id: int
    household_id: int
    email: str
    expires_at: datetime
    link: str


# ---------- Chores ----------

class ChoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


