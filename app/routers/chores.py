from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Chore, Member, Phase, User
from app.routers.households import get_household_or_404
from app.schemas import ChoreCreate, ChoreRead

router = APIRouter(tags=["chores"])


@router.post("/households/{household_id}/chores", status_code=201)
def create_chore(
    household_id: int,
    body: ChoreCreate,
    x_user_email: str = Header(),
    session: Session = Depends(get_session),
) -> ChoreRead:
    household = get_household_or_404(session, household_id)
    if household.phase != Phase.SETUP:
        raise HTTPException(status_code=409, detail="Chores can only be added in SETUP")

    creator = session.exec(
        select(Member)
        .join(User, Member.user_id == User.id)
        .where(Member.household_id == household_id, User.email == x_user_email)
    ).first()
    if creator is None:
        raise HTTPException(status_code=403, detail="You are not a member of this household")

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
