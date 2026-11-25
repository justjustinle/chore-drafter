"""The shapes of data going in and out of the API.

*Create models are what the client sends.
*Read models are what the server sends back.

Create models use extra="forbid": a field the model does not declare
(for example a typo like "colur", or "phase") is rejected with a 422
instead of being silently ignored.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Phase


# ---------- Households ----------

class HouseholdCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)


class MemberRead(BaseModel):
    id: int
    display_name: str
    email: str
    turn_order: int
    joined_at: datetime


class ChoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # can be built straight from a Chore row

    id: int
    household_id: int
    name: str
    description: str | None
    effort_points: int | None
    created_by: int


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
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class InviteRead(BaseModel):
    id: int
    household_id: int
    email: str
    expires_at: datetime
    link: str


# ---------- Chores ----------

class ChoreCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
