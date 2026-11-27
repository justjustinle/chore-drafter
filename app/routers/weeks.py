from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.identity import get_caller_email, require_member, require_owner
from app.models import Household, Week, WeekChore, WeekStatus
from app.routers.households import get_household_or_404
from app.schemas import (
    Assignments,
    AuctionState,
    BidRequest,
    EstimationStatus,
    FlagCreate,
    FlagsRead,
    HistoryWeek,
    NominateRequest,
    PassRequest,
    WeekChoreRead,
    WeekCreate,
    WeekRead,
)
from app.services import auction, estimation, results, weeks

router = APIRouter(tags=["weeks"])


def household_of(session: Session, week: Week) -> Household:
    return session.get(Household, week.household_id)


@router.post("/households/{household_id}/weeks", status_code=201)
def open_week(
    household_id: int,
    body: WeekCreate,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> WeekRead:
    household = get_household_or_404(session, household_id)
    require_member(session, household_id, caller)
    week = weeks.open_week(session, household, body.starts_on)
    return weeks.week_read(session, week)


@router.get("/weeks/{week_id}")
def get_week(
    week_id: int, caller: str = Depends(get_caller_email), session: Session = Depends(get_session)
) -> WeekRead:
    week = weeks.get_week_or_404(session, week_id)
    require_member(session, week.household_id, caller)
    return weeks.week_read(session, week)


@router.post("/weeks/{week_id}/flags")
def flag_chore(
    week_id: int,
    body: FlagCreate,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> FlagsRead:
    week = weeks.get_week_or_404(session, week_id)
    member = require_member(session, week.household_id, caller)
    flagged = weeks.flag_chore(session, week, member, body.chore_id)
    return FlagsRead(week_id=week.id, flagged_chore_ids=flagged)


@router.post("/weeks/{week_id}/estimation/start", status_code=201)
def start_re_estimation(
    week_id: int, caller: str = Depends(get_caller_email), session: Session = Depends(get_session)
) -> EstimationStatus:
    week = weeks.get_week_or_404(session, week_id)
    household = household_of(session, week)
    require_owner(session, household, caller)
    weeks.start_re_estimation(session, household, week)
    return estimation.estimation_status(session, household.id)


@router.post("/weeks/{week_id}/auction/start")
def start_auction(
    week_id: int, caller: str = Depends(get_caller_email), session: Session = Depends(get_session)
) -> AuctionState:
    week = weeks.get_week_or_404(session, week_id, lock=True)
    household = household_of(session, week)
    require_owner(session, household, caller)
    weeks.start_auction(session, household, week)
    return auction.auction_state(session, week)


@router.get("/weeks/{week_id}/auction")
def get_auction(
    week_id: int, caller: str = Depends(get_caller_email), session: Session = Depends(get_session)
) -> AuctionState:
    week = auction.lock_week(session, week_id)  # also applies any expired turns
    require_member(session, week.household_id, caller)
    if week.status not in (WeekStatus.AUCTION, WeekStatus.ASSIGNED):
        raise HTTPException(status_code=409, detail="The auction has not started")
    session.commit()
    return auction.auction_state(session, week)


@router.post("/weeks/{week_id}/auction/nominate")
def nominate(
    week_id: int,
    body: NominateRequest,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> AuctionState:
    week = auction.lock_week(session, week_id)
    member = require_member(session, week.household_id, caller)
    auction.nominate(session, week, member, body.chore_id, body.opening_bid, body.turn_number)
    return auction.auction_state(session, week)


@router.post("/weeks/{week_id}/auction/bid")
def bid(
    week_id: int,
    body: BidRequest,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> AuctionState:
    week = auction.lock_week(session, week_id)
    member = require_member(session, week.household_id, caller)
    auction.bid(session, week, member, body.amount, body.turn_number)
    return auction.auction_state(session, week)


@router.post("/weeks/{week_id}/auction/pass")
def pass_turn(
    week_id: int,
    body: PassRequest,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> AuctionState:
    week = auction.lock_week(session, week_id)
    member = require_member(session, week.household_id, caller)
    auction.pass_turn(session, week, member, body.turn_number)
    return auction.auction_state(session, week)


@router.post("/weeks/{week_id}/finish")
def finish_week(
    week_id: int, caller: str = Depends(get_caller_email), session: Session = Depends(get_session)
) -> Assignments:
    week = weeks.get_week_or_404(session, week_id, lock=True)
    household = household_of(session, week)
    require_owner(session, household, caller)
    results.finish(session, household, week)
    return results.assignments(session, week)


@router.get("/weeks/{week_id}/assignments")
def get_assignments(
    week_id: int, caller: str = Depends(get_caller_email), session: Session = Depends(get_session)
) -> Assignments:
    week = weeks.get_week_or_404(session, week_id)
    require_member(session, week.household_id, caller)
    return results.assignments(session, week)


@router.post("/week-chores/{week_chore_id}/done")
def mark_done(
    week_chore_id: int, caller: str = Depends(get_caller_email), session: Session = Depends(get_session)
) -> WeekChoreRead:
    week_chore = session.get(WeekChore, week_chore_id)
    if week_chore is None:
        raise HTTPException(status_code=404, detail="Chore not found")
    week = session.get(Week, week_chore.week_id)
    member = require_member(session, week.household_id, caller)
    results.mark_done(session, week_chore_id, member)
    return next(c for c in weeks.week_chore_reads(session, week.id) if c.id == week_chore_id)


@router.post("/weeks/{week_id}/close")
def close_week(
    week_id: int, caller: str = Depends(get_caller_email), session: Session = Depends(get_session)
) -> WeekRead:
    week = weeks.get_week_or_404(session, week_id, lock=True)
    require_owner(session, household_of(session, week), caller)
    results.close_week(session, week)
    return weeks.week_read(session, week)


@router.get("/households/{household_id}/history")
def get_history(
    household_id: int, caller: str = Depends(get_caller_email), session: Session = Depends(get_session)
) -> list[HistoryWeek]:
    get_household_or_404(session, household_id)
    require_member(session, household_id, caller)
    return results.history(session, household_id)
