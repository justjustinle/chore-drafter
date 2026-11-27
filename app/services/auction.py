"""The live auction: nominate, bid, pass, and the lazy turn timer.

The actions (nominate, bid, pass) do not commit. The router commits once,
together with the Idempotency-Key record (Layer 6), so the action and the
saved response are stored together or not at all.

Every request starts by locking the week row (SELECT ... FOR UPDATE).
Two requests for the same week are therefore handled one after the other,
never interleaved. The turn_number checks then reject whichever request
arrived second, and unique (lot_id, turn_number) on auction_action is the
last line of defence if the code ever gets that wrong.

The rules decide `at` (when something happened). Normally that is now, but
when the timer catches up on a turn that expired earlier, `at` is the old
deadline, so each later turn still gets its fair 30 seconds.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import clock
from app.game.auction import (
    next_bidder,
    next_in_rotation,
    skip_timed_out_nominations,
    tokens_left,
)
from app.game.rules import TURN_LENGTH, TURN_SECONDS
from app.models import (
    ActionKind,
    AssignedVia,
    AuctionAction,
    AuctionLot,
    Chore,
    LotStatus,
    Member,
    Week,
    WeekChore,
    WeekStatus,
)
from app.schemas import AuctionState, LotState, MemberTokens, NominationState
from app.services.weeks import get_week_or_404, week_chore_reads, week_members

# ---------- Reading the state ----------


def open_lot(session: Session, week_id: int) -> AuctionLot | None:
    return session.exec(
        select(AuctionLot).where(AuctionLot.week_id == week_id, AuctionLot.status == LotStatus.OPEN)
    ).first()


def turn_order(session: Session, week: Week) -> list[int]:
    return [member.id for member in week_members(session, week)]


def chores_nominated(session: Session, week_id: int) -> int:
    return session.exec(select(func.count()).select_from(AuctionLot).where(AuctionLot.week_id == week_id)).one()


def tokens_spent(session: Session, week_id: int, member_id: int) -> int:
    spent = session.exec(
        select(func.sum(WeekChore.price_paid)).where(
            WeekChore.week_id == week_id, WeekChore.assigned_member_id == member_id
        )
    ).one()
    return spent or 0


def member_tokens_left(session: Session, week_id: int, member_id: int) -> int:
    """Calculated, never stored, so it can never drift from the facts."""
    return tokens_left(chores_nominated(session, week_id), tokens_spent(session, week_id, member_id))


def auction_state(session: Session, week: Week) -> AuctionState:
    nomination = None
    lot_state = None
    lot = open_lot(session, week.id)
    if lot is not None:
        week_chore = session.get(WeekChore, lot.week_chore_id)
        chore = session.get(Chore, week_chore.chore_id)
        lot_state = LotState(
            lot_id=lot.id,
            chore_id=chore.id,
            chore_name=chore.name,
            effort_points=week_chore.effort_points,
            nominated_by=lot.nominated_by,
            high_bid=lot.high_bid,
            high_bidder_id=lot.high_bidder_id,
            turn_member_id=lot.turn_member_id,
            turn_number=lot.turn_number,
            turn_deadline=lot.turn_deadline,
        )
    elif week.status == WeekStatus.AUCTION:
        nomination = NominationState(
            member_id=week.nomination_member_id,
            turn_number=week.nomination_turn,
            deadline=week.nomination_deadline,
        )

    members = []
    for member in week_members(session, week):
        won = session.exec(
            select(func.sum(WeekChore.effort_points)).where(
                WeekChore.week_id == week.id, WeekChore.assigned_member_id == member.id
            )
        ).one()
        members.append(
            MemberTokens(
                member_id=member.id,
                display_name=member.display_name,
                tokens_left=member_tokens_left(session, week.id, member.id),
                effort_won=won or 0,
            )
        )

    return AuctionState(
        week_id=week.id,
        status=week.status,
        nomination=nomination,
        lot=lot_state,
        members=members,
        unsold_chores=week_chore_reads(session, week.id, only_unsold=True),
    )


# ---------- Moving the auction on ----------


def record_action(
    session: Session,
    lot: AuctionLot,
    member_id: int,
    kind: ActionKind,
    amount: int | None = None,
    timed_out: bool = False,
    at: datetime | None = None,
) -> None:
    session.add(
        AuctionAction(
            lot_id=lot.id,
            member_id=member_id,
            kind=kind,
            amount=amount,
            turn_number=lot.turn_number,
            timed_out=timed_out,
            created_at=at or clock.now(),
        )
    )
    try:
        session.flush()  # the unique (lot_id, turn_number) check happens here
    except IntegrityError:
        # Last line of defence: the lock and turn checks should make this
        # impossible, but if two actions for one turn ever get this far, the
        # database refuses the second and the caller gets a clean 409.
        raise HTTPException(status_code=409, detail="That turn has already been taken") from None
    lot.turn_number += 1


def advance_lot(session: Session, week: Week, lot: AuctionLot, at: datetime) -> None:
    """Hand the turn to the next bidder, or sell the chore if nobody is left.

    A member who cannot afford to beat the high bid passes automatically.
    """
    order = turn_order(session, week)
    passed = set(
        session.exec(
            select(AuctionAction.member_id).where(
                AuctionAction.lot_id == lot.id, AuctionAction.kind == ActionKind.PASS
            )
        ).all()
    )
    while True:
        candidate = next_bidder(order, lot.turn_member_id, passed, lot.high_bidder_id)
        if candidate is None:
            sell(session, week, lot, at)
            return
        lot.turn_member_id = candidate
        if member_tokens_left(session, week.id, candidate) < lot.high_bid + 1:
            record_action(session, lot, candidate, ActionKind.PASS, at=at)
            passed.add(candidate)
            continue
        lot.turn_deadline = at + TURN_LENGTH
        return


def sell(session: Session, week: Week, lot: AuctionLot, at: datetime) -> None:
    lot.status = LotStatus.SOLD
    lot.turn_member_id = None
    lot.turn_deadline = None

    week_chore = session.get(WeekChore, lot.week_chore_id)
    week_chore.assigned_member_id = lot.high_bidder_id
    week_chore.assigned_via = AssignedVia.AUCTION
    week_chore.price_paid = lot.high_bid
    session.flush()

    unsold = session.exec(
        select(WeekChore).where(WeekChore.week_id == week.id, WeekChore.assigned_member_id.is_(None))
    ).first()
    if unsold is None:
        # Every chore is sold: the auction is over.
        week.status = WeekStatus.ASSIGNED
        week.nomination_member_id = None
        week.nomination_deadline = None
        return

    week.nomination_member_id = next_in_rotation(turn_order(session, week), lot.nominated_by)
    week.nomination_turn += 1
    week.nomination_deadline = at + TURN_LENGTH


def apply_timeouts(session: Session, week: Week) -> None:
    """The lazy timer. No background job counts down the 30 seconds; instead,
    every auction request first checks whether a deadline has passed and, if
    so, records what should have happened (a pass, or a skipped nomination)."""
    now = clock.now()
    while week.status == WeekStatus.AUCTION:
        lot = open_lot(session, week.id)
        if lot is not None:
            if lot.turn_deadline >= now:
                return
            at = lot.turn_deadline
            record_action(session, lot, lot.turn_member_id, ActionKind.PASS, timed_out=True, at=at)
            advance_lot(session, week, lot, at)
            continue  # the next turn may have expired too
        member, skipped, deadline = skip_timed_out_nominations(
            turn_order(session, week),
            week.nomination_member_id,
            week.nomination_deadline,
            now,
            TURN_SECONDS,
        )
        week.nomination_member_id = member
        week.nomination_turn += skipped
        week.nomination_deadline = deadline
        return


def lock_week(session: Session, week_id: int) -> Week:
    """Lock the week row and catch up on any turns that have expired."""
    week = get_week_or_404(session, week_id, lock=True)
    apply_timeouts(session, week)
    return week


def require_auction(week: Week) -> None:
    if week.status != WeekStatus.AUCTION:
        raise HTTPException(status_code=409, detail="The auction is not running")


# ---------- The actions ----------


def nominate(
    session: Session, week: Week, member: Member, chore_id: int, opening_bid: int, turn_number: int
) -> None:
    require_auction(week)
    if open_lot(session, week.id) is not None:
        raise HTTPException(status_code=409, detail="A chore is already being auctioned")
    if turn_number != week.nomination_turn:
        raise HTTPException(status_code=409, detail="That turn has already moved on")
    if member.id != week.nomination_member_id:
        raise HTTPException(status_code=403, detail="It is not your turn to nominate")

    week_chore = session.exec(
        select(WeekChore).where(WeekChore.week_id == week.id, WeekChore.chore_id == chore_id)
    ).first()
    if week_chore is None:
        raise HTTPException(status_code=404, detail="Chore not found in this week")
    if week_chore.assigned_member_id is not None:
        raise HTTPException(status_code=409, detail="That chore is already sold")

    # Everyone gets +1 token as part of nominating, so count this lot first.
    budget = tokens_left(chores_nominated(session, week.id) + 1, tokens_spent(session, week.id, member.id))
    if opening_bid > budget:
        raise HTTPException(status_code=409, detail=f"Not enough tokens: you have {budget}")

    now = clock.now()
    lot = AuctionLot(
        week_id=week.id,
        week_chore_id=week_chore.id,
        nominated_by=member.id,
        high_bid=opening_bid,
        high_bidder_id=member.id,
        turn_member_id=member.id,
        turn_number=0,
    )
    session.add(lot)
    session.flush()
    record_action(session, lot, member.id, ActionKind.BID, amount=opening_bid, at=now)  # turn 0
    week.nomination_deadline = None
    advance_lot(session, week, lot, now)


def _require_bidding_turn(session: Session, week: Week, member: Member, turn_number: int) -> AuctionLot:
    require_auction(week)
    lot = open_lot(session, week.id)
    if lot is None:
        raise HTTPException(status_code=409, detail="No chore is being auctioned")
    # Check the turn number first: a late or repeated request for a turn that
    # has moved on is a 409, whoever sent it.
    if turn_number != lot.turn_number:
        raise HTTPException(status_code=409, detail="That turn has already moved on")
    if member.id != lot.turn_member_id:
        raise HTTPException(status_code=403, detail="It is not your turn")
    return lot


def bid(session: Session, week: Week, member: Member, amount: int, turn_number: int) -> None:
    lot = _require_bidding_turn(session, week, member, turn_number)
    if amount <= lot.high_bid:
        raise HTTPException(status_code=409, detail=f"Bid more than {lot.high_bid}")
    budget = member_tokens_left(session, week.id, member.id)
    if amount > budget:
        raise HTTPException(status_code=409, detail=f"Not enough tokens: you have {budget}")

    now = clock.now()
    record_action(session, lot, member.id, ActionKind.BID, amount=amount, at=now)
    lot.high_bid = amount
    lot.high_bidder_id = member.id
    advance_lot(session, week, lot, now)


def pass_turn(session: Session, week: Week, member: Member, turn_number: int) -> None:
    lot = _require_bidding_turn(session, week, member, turn_number)
    now = clock.now()
    record_action(session, lot, member.id, ActionKind.PASS, at=now)
    advance_lot(session, week, lot, now)
