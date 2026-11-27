from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.identity import get_caller_email, require_member
from app.models import Chore, Phase
from app.routers.households import get_household_or_404
from app.schemas import ChoreCreate, ChoreRead

router = APIRouter(tags=["chores"])


@router.post("/households/{household_id}/chores", status_code=201)
def create_chore(
    household_id: int,
    body: ChoreCreate,
    caller: str = Depends(get_caller_email),
    session: Session = Depends(get_session),
) -> ChoreRead:
    household = get_household_or_404(session, household_id)
    if household.phase != Phase.SETUP:
        raise HTTPException(status_code=409, detail="Chores can only be added in SETUP")

    creator = require_member(session, household_id, caller)

    chore = Chore(
        household_id=household_id,
        name=body.name,
        description=body.description,
        created_by=creator.id,
    )
    session.add(chore)
    session.commit()
    return ChoreRead.model_validate(chore)


@router.get("/households/{household_id}/chores")
def list_chores(household_id: int, session: Session = Depends(get_session)) -> list[ChoreRead]:
    get_household_or_404(session, household_id)
    chores = session.exec(
        select(Chore).where(Chore.household_id == household_id).order_by(Chore.id)
    ).all()
    return [ChoreRead.model_validate(chore) for chore in chores]
