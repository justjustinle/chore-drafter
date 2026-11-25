from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Chore, Household, Member, User
from app.schemas import ChoreRead, HouseholdCreate, HouseholdRead, MemberRead

router = APIRouter(tags=["households"])


def get_household_or_404(session: Session, household_id: int) -> Household:
    household = session.get(Household, household_id)
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


def get_or_create_user(session: Session, email: str, name: str) -> User:
    """One user per email address, shared by every household they join."""
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email, first_name=name)
        session.add(user)
        session.flush()  # sends the INSERT now, so user.id is filled in
    return user


def household_to_read(session: Session, household: Household) -> HouseholdRead:
    # Join member to user, because the email lives on user.
    rows = session.exec(
        select(Member, User)
        .join(User, Member.user_id == User.id)
        .where(Member.household_id == household.id)
        .order_by(Member.turn_order)
    ).all()
    members = [
        MemberRead(
            id=member.id,
            display_name=member.display_name,
            email=user.email,
            turn_order=member.turn_order,
            joined_at=member.joined_at,
        )
        for member, user in rows
    ]
    chores = session.exec(
        select(Chore).where(Chore.household_id == household.id).order_by(Chore.id)
    ).all()
    return HouseholdRead(
        id=household.id,
        name=household.name,
        phase=household.phase,
        owner_member_id=household.owner_member_id,
        created_at=household.created_at,
        members=members,
        chores=[ChoreRead.model_validate(chore) for chore in chores],
    )


@router.post("/households", status_code=201)
def create_household(
    body: HouseholdCreate,
    x_user_email: str = Header(),
    x_user_name: str = Header(),
    session: Session = Depends(get_session),
) -> HouseholdRead:
    user = get_or_create_user(session, x_user_email, x_user_name)

    # The household and its owner point at each other, so: create the household,
    # then the member, then fill in the owner. One commit saves all of it, or none.
    household = Household(name=body.name)
    session.add(household)
    session.flush()

    owner = Member(
        household_id=household.id,
        user_id=user.id,
        display_name=x_user_name,
        turn_order=1,
    )
    session.add(owner)
    session.flush()

    household.owner_member_id = owner.id
    session.commit()
    return household_to_read(session, household)


@router.get("/households/{household_id}")
def get_household(household_id: int, session: Session = Depends(get_session)) -> HouseholdRead:
    household = get_household_or_404(session, household_id)
    return household_to_read(session, household)
