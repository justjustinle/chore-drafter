"""Database tables. Each class with `table=True` is one Postgres table.

The design is explained in docs/data-model.md.

Patterns used throughout:
- `Field(primary_key=True)` makes the id; Postgres fills it in.
- `Field(foreign_key="member.id")` makes a column point at another table.
- `UniqueConstraint(...)` in `__table_args__` stops duplicate rows.
- `X | None` means the column may be empty (NULL).
"""

from datetime import date, datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app import clock


def utc_now() -> datetime:
    return clock.now()


def enum_column(enum: type[StrEnum]) -> sa.Enum:
    """Store an enum as plain text with a check on the allowed values."""
    return sa.Enum(enum, native_enum=False, length=20)


# Every datetime is stored with its time zone, so comparisons are never ambiguous.
TIMESTAMP = sa.DateTime(timezone=True)


# ---------- Enums ----------

class Phase(StrEnum):
    SETUP = "SETUP"
    ESTIMATION = "ESTIMATION"
    ACTIVE = "ACTIVE"


class WeekStatus(StrEnum):
    OPEN = "OPEN"
    AUCTION = "AUCTION"
    ASSIGNED = "ASSIGNED"
    CLOSED = "CLOSED"


class AssignedVia(StrEnum):
    AUCTION = "AUCTION"
    FINISH = "FINISH"


class LotStatus(StrEnum):
    OPEN = "OPEN"
    SOLD = "SOLD"


class ActionKind(StrEnum):
    BID = "BID"
    PASS = "PASS"


# ---------- Setup ----------

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, max_length=320)
    first_name: str = Field(max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=utc_now, sa_type=TIMESTAMP)


class Household(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    phase: Phase = Field(default=Phase.SETUP, sa_type=enum_column(Phase))
    # Empty for a moment while the household and its owner are created together.
    # household -> member and member -> household point at each other, so this
    # foreign key is added after both tables exist (use_alter).
    owner_member_id: int | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("member.id", use_alter=True, name="fk_household_owner_member_id"),
            nullable=True,
        ),
    )
    created_at: datetime = Field(default_factory=utc_now, sa_type=TIMESTAMP)


class Member(SQLModel, table=True):
    __table_args__ = (sa.UniqueConstraint("household_id", "user_id"),)

    id: int | None = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="household.id")
    user_id: int = Field(foreign_key="user.id")
    display_name: str = Field(max_length=100)
    turn_order: int
    joined_at: datetime = Field(default_factory=utc_now, sa_type=TIMESTAMP)


class Invite(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="household.id")
    email: str = Field(max_length=320)
    token: str = Field(unique=True, max_length=100)
    invited_by: int | None = Field(default=None, foreign_key="member.id")  # set from Layer 8
    expires_at: datetime = Field(sa_type=TIMESTAMP)
    accepted_at: datetime | None = Field(default=None, sa_type=TIMESTAMP)


class Chore(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="household.id")
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    effort_points: int | None = None  # empty until the first estimation closes
    created_by: int = Field(foreign_key="member.id")


# ---------- Estimation ----------

class EstimationRound(SQLModel, table=True):
    __tablename__ = "estimation_round"
    __table_args__ = (
        # At most one open round per household: a "partial" unique index that
        # only covers rows where closed_at is empty.
        sa.Index(
            "one_open_round_per_household",
            "household_id",
            unique=True,
            postgresql_where=sa.text("closed_at IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="household.id")
    week_id: int | None = Field(default=None, foreign_key="week.id")  # empty for the first round
    opened_at: datetime = Field(default_factory=utc_now, sa_type=TIMESTAMP)
    closed_at: datetime | None = Field(default=None, sa_type=TIMESTAMP)
    force_closed: bool = False


class EffortVote(SQLModel, table=True):
    __tablename__ = "effort_vote"
    __table_args__ = (
        sa.UniqueConstraint("round_id", "chore_id", "member_id"),
        sa.CheckConstraint("points BETWEEN 1 AND 10", name="points_1_to_10"),
    )

    id: int | None = Field(default=None, primary_key=True)
    round_id: int = Field(foreign_key="estimation_round.id")
    chore_id: int = Field(foreign_key="chore.id")
    member_id: int = Field(foreign_key="member.id")
    points: int


# ---------- Weeks ----------

class Week(SQLModel, table=True):
    __table_args__ = (sa.UniqueConstraint("household_id", "starts_on"),)

    id: int | None = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="household.id")
    starts_on: date
    opened_at: datetime = Field(default_factory=utc_now, sa_type=TIMESTAMP)
    status: WeekStatus = Field(default=WeekStatus.OPEN, sa_type=enum_column(WeekStatus))
    nomination_member_id: int | None = Field(default=None, foreign_key="member.id")
    nomination_turn: int = 0
    nomination_deadline: datetime | None = Field(default=None, sa_type=TIMESTAMP)


class ChoreFlag(SQLModel, table=True):
    __tablename__ = "chore_flag"
    __table_args__ = (sa.UniqueConstraint("week_id", "chore_id", "member_id"),)

    id: int | None = Field(default=None, primary_key=True)
    week_id: int = Field(foreign_key="week.id")
    chore_id: int = Field(foreign_key="chore.id")
    member_id: int = Field(foreign_key="member.id")


class WeekChore(SQLModel, table=True):
    __tablename__ = "week_chore"
    __table_args__ = (sa.UniqueConstraint("week_id", "chore_id"),)

    id: int | None = Field(default=None, primary_key=True)
    week_id: int = Field(foreign_key="week.id")
    chore_id: int = Field(foreign_key="chore.id")
    effort_points: int  # snapshot, copied from chore when the week opens
    assigned_member_id: int | None = Field(default=None, foreign_key="member.id")
    assigned_via: AssignedVia | None = Field(default=None, sa_type=enum_column(AssignedVia))
    price_paid: int | None = None
    done_at: datetime | None = Field(default=None, sa_type=TIMESTAMP)


# ---------- Auction ----------

class AuctionLot(SQLModel, table=True):
    __tablename__ = "auction_lot"
    __table_args__ = (
        sa.Index(
            "one_open_lot_per_week",
            "week_id",
            unique=True,
            postgresql_where=sa.text("status = 'OPEN'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    week_id: int = Field(foreign_key="week.id")
    week_chore_id: int = Field(foreign_key="week_chore.id", unique=True)
    nominated_by: int = Field(foreign_key="member.id")
    status: LotStatus = Field(default=LotStatus.OPEN, sa_type=enum_column(LotStatus))
    high_bid: int
    high_bidder_id: int = Field(foreign_key="member.id")
    turn_member_id: int | None = Field(default=None, foreign_key="member.id")
    turn_number: int = 0
    turn_deadline: datetime | None = Field(default=None, sa_type=TIMESTAMP)


class AuctionAction(SQLModel, table=True):
    __tablename__ = "auction_action"
    __table_args__ = (sa.UniqueConstraint("lot_id", "turn_number"),)

    id: int | None = Field(default=None, primary_key=True)
    lot_id: int = Field(foreign_key="auction_lot.id")
    member_id: int = Field(foreign_key="member.id")
    kind: ActionKind = Field(sa_type=enum_column(ActionKind))
    amount: int | None = None  # empty for a pass
    turn_number: int
    timed_out: bool = False
    created_at: datetime = Field(default_factory=utc_now, sa_type=TIMESTAMP)


# ---------- Reliability ----------

class IdempotencyRecord(SQLModel, table=True):
    """The saved response for a request sent with an Idempotency-Key header.

    If the same member sends the same key again (a retry after a timeout, a
    double-tap), the server returns this saved response instead of acting twice.
    """

    __tablename__ = "idempotency_record"
    __table_args__ = (sa.UniqueConstraint("member_id", "key"),)

    id: int | None = Field(default=None, primary_key=True)
    member_id: int = Field(foreign_key="member.id")
    key: str = Field(max_length=100)
    path: str = Field(max_length=200)
    status_code: int
    response_body: dict = Field(sa_type=sa.JSON)
    created_at: datetime = Field(default_factory=utc_now, sa_type=TIMESTAMP)
