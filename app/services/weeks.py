"""Weeks: opening a week, flags and re-estimation, starting the auction."""

from datetime import date

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app import clock
from app.game.auction import first_nominator
from app.game.rules import TURN_LENGTH
from app.models import (
    Chore,
    ChoreFlag,
    EstimationRound,
    Household,
    Member,
    Phase,
    Week,
    WeekChore,
    WeekStatus,
)
from app.schemas import WeekChoreRead, WeekRead
from app.services.estimation import get_open_round


def get_week_or_404(session: Session, week_id: int, lock: bool = False) -> Week:
    query = select(Week).where(Week.id == week_id)
    if lock:
        query = query.with_for_update()
    week = session.exec(query).first()
    if week is None:
        raise HTTPException(status_code=404, detail="Week not found")
    return week


def week_members(session: Session, week: Week) -> list[Member]:
    """The members playing this week: everyone who had joined when it opened."""
    return list(
        session.exec(
            select(Member)
            .where(Member.household_id == week.household_id, Member.joined_at <= week.opened_at)
            .order_by(Member.turn_order)
        ).all()
    )


def require_week_member(session: Session, week: Week, member: Member) -> None:
    if member.id not in {m.id for m in week_members(session, week)}:
        raise HTTPException(status_code=403, detail="You joined after this week opened")


def week_chore_reads(session: Session, week_id: int, only_unsold: bool = False) -> list[WeekChoreRead]:
    query = (
        select(WeekChore, Chore)
        .join(Chore, WeekChore.chore_id == Chore.id)
        .where(WeekChore.week_id == week_id)
        .order_by(WeekChore.id)
    )
    if only_unsold:
        query = query.where(WeekChore.assigned_member_id.is_(None))
    return [
        WeekChoreRead(
            id=week_chore.id,
            chore_id=chore.id,
            name=chore.name,
            effort_points=week_chore.effort_points,
            assigned_member_id=week_chore.assigned_member_id,
            assigned_via=week_chore.assigned_via,
            price_paid=week_chore.price_paid,
            done_at=week_chore.done_at,
        )
        for week_chore, chore in session.exec(query).all()
    ]


def week_read(session: Session, week: Week) -> WeekRead:
    return WeekRead(
        id=week.id,
        household_id=week.household_id,
        starts_on=week.starts_on,
        status=week.status,
        chores=week_chore_reads(session, week.id),
    )


def open_week(session: Session, household: Household, starts_on: date | None) -> Week:
    if household.phase != Phase.ACTIVE:
        raise HTTPException(status_code=409, detail="Weeks can only open once estimation is done")
    unfinished = session.exec(
        select(Week).where(Week.household_id == household.id, Week.status != WeekStatus.CLOSED)
    ).first()
    if unfinished is not None:
        raise HTTPException(status_code=409, detail="The current week is not closed yet")

    starts_on = starts_on or clock.now().date()
    clash = session.exec(
        select(Week).where(Week.household_id == household.id, Week.starts_on == starts_on)
    ).first()
    if clash is not None:
        raise HTTPException(status_code=409, detail="A week already starts on that date")

    week = Week(household_id=household.id, starts_on=starts_on, opened_at=clock.now())
    session.add(week)
    session.flush()

    # Snapshot: copy each chore's current effort into this week. History
    # keeps these numbers even if the chore is re-estimated later.
    chores = session.exec(select(Chore).where(Chore.household_id == household.id)).all()
    for chore in chores:
        session.add(WeekChore(week_id=week.id, chore_id=chore.id, effort_points=chore.effort_points))
    session.commit()
    return week


def flag_chore(session: Session, week: Week, member: Member, chore_id: int) -> list[int]:
    if week.status != WeekStatus.OPEN:
        raise HTTPException(status_code=409, detail="Chores can only be flagged before the auction")
    require_week_member(session, week, member)
    chore = session.get(Chore, chore_id)
    if chore is None or chore.household_id != week.household_id:
        raise HTTPException(status_code=404, detail="Chore not found")

    # Flagging twice is harmless: the unique constraint makes the second a no-op.
    statement = insert(ChoreFlag).values(week_id=week.id, chore_id=chore_id, member_id=member.id)
    session.execute(statement.on_conflict_do_nothing())
    session.commit()
    return flagged_chore_ids(session, week.id)


def flagged_chore_ids(session: Session, week_id: int) -> list[int]:
    ids = session.exec(select(ChoreFlag.chore_id).where(ChoreFlag.week_id == week_id)).all()
    return sorted(set(ids))


def start_re_estimation(session: Session, household: Household, week: Week) -> EstimationRound:
    if week.status != WeekStatus.OPEN:
        raise HTTPException(status_code=409, detail="Re-estimation happens before the auction")
    if not flagged_chore_ids(session, week.id):
        raise HTTPException(status_code=409, detail="No chores are flagged")
    if get_open_round(session, household.id) is not None:
        raise HTTPException(status_code=409, detail="An estimation is already open")

    estimation_round = EstimationRound(household_id=household.id, week_id=week.id, opened_at=clock.now())
    session.add(estimation_round)
    session.commit()
    return estimation_round


def start_auction(session: Session, household: Household, week: Week) -> None:
    if week.status != WeekStatus.OPEN:
        raise HTTPException(status_code=409, detail="The auction has already started")
    if get_open_round(session, household.id) is not None:
        raise HTTPException(status_code=409, detail="Finish the re-estimation first")
    if flagged_chore_ids(session, week.id):
        re_estimated = session.exec(
            select(EstimationRound).where(
                EstimationRound.week_id == week.id, EstimationRound.closed_at.is_not(None)
            )
        ).first()
        if re_estimated is None:
            raise HTTPException(status_code=409, detail="Flagged chores must be re-estimated first")

    order = [member.id for member in week_members(session, week)]
    earlier_weeks = session.exec(
        select(Week).where(Week.household_id == household.id, Week.opened_at < week.opened_at)
    ).all()

    week.status = WeekStatus.AUCTION
    week.nomination_member_id = first_nominator(order, len(earlier_weeks))
    week.nomination_turn = 1
    week.nomination_deadline = clock.now() + TURN_LENGTH
    session.commit()

