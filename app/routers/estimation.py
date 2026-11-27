from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.identity import get_caller_email, require_member, require_owner
from app.routers.households import get_household_or_404
from app.schemas import EstimationResult, EstimationStatus, VoteCreate, VoteRead
from app.services import estimation

router = APIRouter(tags=["estimation"])


@router.post("/households/{household_id}/estimation/start", status_code=201)
def start_estimation(
    household_id: int,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> EstimationStatus:
    household = get_household_or_404(session, household_id)
    require_owner(session, household, caller)
    estimation.start_first_estimation(session, household)
    return estimation.estimation_status(session, household_id)


@router.put("/households/{household_id}/estimation/votes/{chore_id}")
def vote(
    household_id: int,
    chore_id: int,
    body: VoteCreate,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> VoteRead:
    household = get_household_or_404(session, household_id)
    voter = require_member(session, household_id, caller)
    closed = estimation.cast_vote(session, household, voter, chore_id, body.points)
    return VoteRead(chore_id=chore_id, points=body.points, estimation_closed=closed)


@router.get("/households/{household_id}/estimation")
def get_estimation(
    household_id: int,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> EstimationStatus:
    get_household_or_404(session, household_id)
    require_member(session, household_id, caller)
    return estimation.estimation_status(session, household_id)


@router.post("/households/{household_id}/estimation/close")
def close_estimation(
    household_id: int,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> EstimationResult:
    household = get_household_or_404(session, household_id)
    require_owner(session, household, caller)
    return estimation.force_close(session, household)
