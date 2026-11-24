from fastapi import APIRouter, Header, HTTPException

from app import storage
from app.routers.households import get_household_or_404
from app.schemas import ChoreCreate, ChoreRead, Phase

router = APIRouter(tags=["chores"])


@router.post("/households/{household_id}/chores", status_code=201)
def create_chore(
    household_id: int,
    body: ChoreCreate,
    x_user_email: str = Header(),
) -> ChoreRead:
    household = get_household_or_404(household_id)
    if household.phase != Phase.SETUP:
        raise HTTPException(status_code=409, detail="Chores can only be added in SETUP")

    creator = None
    for m in storage.members.values():
        if m.household_id == household_id and m.email == x_user_email:
            creator = m
    if creator is None:
        raise HTTPException(status_code=403, detail="You are not a member of this household")

    chore = storage.Chore(
        id=storage.next_id(storage.chores),
        household_id=household_id,
        name=body.name,
        description=body.description,
        created_by=creator.id,

    )
    storage.chores[chore.id] = chore
    return ChoreRead(**chore.model_dump())


@router.get("/households/{household_id}/chores")
def list_chores(household_id: int) -> list[ChoreRead]:
    get_household_or_404(household_id)
    return [
        ChoreRead(**c.model_dump())
        for c in storage.chores.values()
        if c.household_id == household_id
    ]
