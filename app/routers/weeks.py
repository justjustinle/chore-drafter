from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.identity import get_caller_email, require_member, require_owner
from app.models import Household, Week, WeekStatus
from app.routers.households import get_household_or_404
from app.schemas import (
    AuctionState,
    BidRequest,
    EstimationStatus,
    FlagCreate,
    FlagsRead,
    NominateRequest,
    PassRequest,
    WeekCreate,
    WeekRead,
)
from app.services import auction, estimation, weeks

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
