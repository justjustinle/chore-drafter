"""After the auction: the finish fallback, assignments, done, close, history.

finish() and close_week() are idempotent: calling them again changes
nothing, so a retry, a double-click or the scheduled job running twice
is always safe.
"""

from fastapi import HTTPException
from sqlmodel import Session, select

from app import clock
from app.game.finish import assign_leftovers
from app.models import AssignedVia, Chore, Household, Member, Week, WeekChore, WeekStatus
from app.schemas import Assignments, HistoryChore, HistoryWeek, MemberEffort
from app.services.auction import apply_timeouts, open_lot, sell
from app.services.estimation import get_open_round
from app.services.weeks import week_chore_reads, week_members


def finish(session: Session, household: Household, week: Week) -> None:
    """Assign every chore that is still unsold. `week` must already be locked."""
    if week.status in (WeekStatus.ASSIGNED, WeekStatus.CLOSED):
        return  # already done: doing nothing is the idempotent answer
    if get_open_round(session, household.id) is not None:
        raise HTTPException(status_code=409, detail="Finish the re-estimation first")

    apply_timeouts(session, week)
    lot = open_lot(session, week.id)
    if lot is not None:
        # A chore is mid-auction: it goes to the current high bidder at their bid.
        sell(session, week, lot, clock.now())

    members = week_members(session, week)
    week_chores = session.exec(select(WeekChore).where(WeekChore.week_id == week.id)).all()
    effort_so_far: dict[int, int] = {}
    for week_chore in week_chores:
        if week_chore.assigned_member_id is not None:
            member = week_chore.assigned_member_id
            effort_so_far[member] = effort_so_far.get(member, 0) + week_chore.effort_points

    # Only chores with no member yet: a second run finds none, so it assigns nothing twice.
    unsold = {wc.id: wc for wc in week_chores if wc.assigned_member_id is None}
    decided = assign_leftovers(
        [(wc.id, wc.effort_points) for wc in unsold.values()],
        [member.id for member in members],
        effort_so_far,
    )
    for week_chore_id, member_id in decided.items():
        unsold[week_chore_id].assigned_member_id = member_id
        unsold[week_chore_id].assigned_via = AssignedVia.FINISH

    week.status = WeekStatus.ASSIGNED
    week.nomination_member_id = None
    week.nomination_deadline = None
    session.commit()


def assignments(session: Session, week: Week) -> Assignments:
    if week.status not in (WeekStatus.ASSIGNED, WeekStatus.CLOSED):
        raise HTTPException(status_code=409, detail="Chores are not assigned yet")
    chores = week_chore_reads(session, week.id)
    members = []
    for member in week_members(session, week):
        mine = [c for c in chores if c.assigned_member_id == member.id]
        members.append(
            MemberEffort(
                member_id=member.id,
                display_name=member.display_name,
                effort=sum(c.effort_points for c in mine),
                tokens_spent=sum(c.price_paid or 0 for c in mine),
            )
        )
    return Assignments(week_id=week.id, status=week.status, chores=chores, members=members)


def mark_done(session: Session, week_chore_id: int, member: Member) -> WeekChore:
    week_chore = session.get(WeekChore, week_chore_id)
    if week_chore is None:
        raise HTTPException(status_code=404, detail="Chore not found")
    week = session.get(Week, week_chore.week_id)
    if week.household_id != member.household_id:
        raise HTTPException(status_code=403, detail="You are not a member of this household")
    if week.status != WeekStatus.ASSIGNED:
        raise HTTPException(status_code=409, detail="Chores can only be marked done during the week")
    if week_chore.assigned_member_id != member.id:
        raise HTTPException(status_code=403, detail="Only the person assigned can mark it done")
    if week_chore.done_at is None:  # marking it done twice keeps the first time
        week_chore.done_at = clock.now()
        session.commit()
    return week_chore


def close_week(session: Session, week: Week) -> None:
    if week.status == WeekStatus.CLOSED:
        return  # idempotent
    if week.status != WeekStatus.ASSIGNED:
        raise HTTPException(status_code=409, detail="Assign every chore before closing the week")
    week.status = WeekStatus.CLOSED
    session.commit()


def history(session: Session, household_id: int) -> list[HistoryWeek]:
    closed_weeks = session.exec(
        select(Week)
        .where(Week.household_id == household_id, Week.status == WeekStatus.CLOSED)
        .order_by(Week.starts_on.desc())
    ).all()
    result = []
    for week in closed_weeks:
        rows = session.exec(
            select(WeekChore, Chore, Member)
            .join(Chore, WeekChore.chore_id == Chore.id)
            .join(Member, WeekChore.assigned_member_id == Member.id, isouter=True)
            .where(WeekChore.week_id == week.id)
            .order_by(WeekChore.id)
        ).all()
        result.append(
            HistoryWeek(
                week_id=week.id,
                starts_on=week.starts_on,
                chores=[
                    HistoryChore(
                        name=chore.name,
                        effort_points=week_chore.effort_points,  # the snapshot, not today's value
                        assigned_to=member.display_name if member else None,
                        assigned_via=week_chore.assigned_via,
                        price_paid=week_chore.price_paid,
                        done=week_chore.done_at is not None,
                    )
                    for week_chore, chore, member in rows
                ],
            )
        )
    return result
