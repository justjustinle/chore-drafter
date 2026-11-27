"""The shapes of data going in and out of the API.

*Create models are what the client sends.
*Read models are what the server sends back.

Create models use extra="forbid": a field the model does not declare
(for example a typo like "colur", or "phase") is rejected with a 422
instead of being silently ignored.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.game.rules import VOTE_MAX, VOTE_MIN
from app.models import AssignedVia, Phase, WeekStatus


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


class HouseholdCreated(HouseholdRead):
    api_key: str  # the owner's key; shown only this once


class MemberCreated(MemberRead):
    api_key: str  # the new member's key; shown only this once


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


# ---------- Estimation ----------

class VoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: int = Field(ge=VOTE_MIN, le=VOTE_MAX)


class VoteRead(BaseModel):
    chore_id: int
    points: int  # your own vote only; other people's votes are never shown
    estimation_closed: bool


class VoterStatus(BaseModel):
    member_id: int
    display_name: str
    voted_chore_ids: list[int]  # which chores they have voted on, never the values
    done: bool


class EstimationStatus(BaseModel):
    round_id: int
    week_id: int | None
    opened_at: datetime
    chore_ids: list[int]
    voters: list[VoterStatus]


class ChoreEffort(BaseModel):
    chore_id: int
    effort_points: int
    vote_count: int


class EstimationResult(BaseModel):
    round_id: int
    closed_at: datetime
    force_closed: bool
    efforts: list[ChoreEffort]


# ---------- Weeks ----------

class WeekCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_on: date | None = None  # defaults to today


class WeekChoreRead(BaseModel):
    id: int
    chore_id: int
    name: str
    effort_points: int  # the value that applies this week
    assigned_member_id: int | None
    assigned_via: AssignedVia | None
    price_paid: int | None
    done_at: datetime | None


class WeekRead(BaseModel):
    id: int
    household_id: int
    starts_on: date
    status: WeekStatus
    chores: list[WeekChoreRead]


class FlagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chore_id: int


class FlagsRead(BaseModel):
    week_id: int
    flagged_chore_ids: list[int]


# ---------- Auction ----------

class NominateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chore_id: int
    opening_bid: int = Field(ge=1)
    turn_number: int


class BidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: int = Field(ge=1)
    turn_number: int


class PassRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_number: int


class NominationState(BaseModel):
    member_id: int
    turn_number: int
    deadline: datetime


class LotState(BaseModel):
    lot_id: int
    chore_id: int
    chore_name: str
    effort_points: int
    nominated_by: int
    high_bid: int
    high_bidder_id: int
    turn_member_id: int
    turn_number: int
    turn_deadline: datetime


class MemberTokens(BaseModel):
    member_id: int
    display_name: str
    tokens_left: int
    effort_won: int


class AuctionState(BaseModel):
    week_id: int
    status: WeekStatus
    nomination: NominationState | None  # set when someone must nominate
    lot: LotState | None  # set while a chore is being bid on
    members: list[MemberTokens]
    unsold_chores: list[WeekChoreRead]


# ---------- Results ----------

class MemberEffort(BaseModel):
    member_id: int
    display_name: str
    effort: int
    tokens_spent: int


class Assignments(BaseModel):
    week_id: int
    status: WeekStatus
    chores: list[WeekChoreRead]
    members: list[MemberEffort]


class HistoryChore(BaseModel):
    name: str
    effort_points: int
    assigned_to: str | None
    assigned_via: AssignedVia | None
    price_paid: int | None
    done: bool


class HistoryWeek(BaseModel):
    week_id: int
    starts_on: date
    chores: list[HistoryChore]
