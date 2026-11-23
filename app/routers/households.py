from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from app import storage
from app.schemas import ChoreRead, HouseholdCreate, HouseholdRead, MemberRead, Phase

router = APIRouter(tags=["households"])


def get_household_or_404(household_id: int) -> storage.Household:
    household = storage.households.get(household_id)
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


def household_to_read(household: storage.Household) -> HouseholdRead:
    household_members = [
        MemberRead(**m.model_dump())
        for m in storage.members.values()
        if m.household_id == household.id
    ]
    household_chores = [
        ChoreRead(**c.model_dump())
        for c in storage.chores.values()
        if c.household_id == household.id
    ]
    return HouseholdRead(
        **household.model_dump(),
        members=household_members,
        chores=household_chores,
    )


@router.post("/households", status_code=201)
def create_household(
    body: HouseholdCreate,
    x_user_email: str = Header(),
    x_user_name: str = Header(),
) -> HouseholdRead:
    now = datetime.now(timezone.utc)
    household_id = storage.next_id(storage.households)
    member_id = storage.next_id(storage.members)

    storage.members[member_id] = storage.Member(
        id=member_id,
        household_id=household_id,
        email=x_user_email,
        display_name=x_user_name,
        turn_order=1,
        joined_at=now,
    )
    household = storage.Household(
        id=household_id,
        name=body.name,
        phase=Phase.SETUP,
        owner_member_id=member_id,
        created_at=now,
    )
    storage.households[household_id] = household
    return household_to_read(household)


@router.get("/households/{household_id}")
def get_household(household_id: int) -> HouseholdRead:
    household = get_household_or_404(household_id)
    return household_to_read(household)
