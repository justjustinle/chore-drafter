"""Estimation: blind voting on effort points.

Services hold the steps that touch the database. They are called by the
routers (for HTTP) and, from Layer 7, by the scheduled job. The maths
lives in app/game/estimation.py and never touches the database.
"""

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app import clock
from app.game.estimation import effort_from_votes, everyone_has_voted
from app.game.rules import MIN_MEMBERS_TO_ESTIMATE
from app.models import (
    Chore,
    ChoreFlag,
    EffortVote,
    EstimationRound,
    Household,
    Member,
    Phase,
    Week,
    WeekChore,
)
from app.schemas import ChoreEffort, EstimationResult, EstimationStatus, VoterStatus


def get_open_round(session: Session, household_id: int, lock: bool = False) -> EstimationRound | None:
    query = select(EstimationRound).where(
        EstimationRound.household_id == household_id,
        EstimationRound.closed_at.is_(None),
    )
    if lock:
        # SELECT ... FOR UPDATE: other requests that also lock this round wait
        # until we commit. Votes are handled one at a time, so the "has
        # everyone voted?" check always sees every earlier vote.
        query = query.with_for_update()
    return session.exec(query).first()


def require_open_round(session: Session, household_id: int, lock: bool = False) -> EstimationRound:
    estimation_round = get_open_round(session, household_id, lock=lock)
    if estimation_round is None:
        raise HTTPException(status_code=409, detail="No estimation is open")
    return estimation_round


def chores_in_round(session: Session, estimation_round: EstimationRound) -> list[Chore]:
    """The first round covers every chore; a re-estimation covers flagged chores."""
    if estimation_round.week_id is None:
        query = select(Chore).where(Chore.household_id == estimation_round.household_id)
    else:
        flagged = select(ChoreFlag.chore_id).where(ChoreFlag.week_id == estimation_round.week_id)
        query = select(Chore).where(Chore.id.in_(flagged))
    return list(session.exec(query.order_by(Chore.id)).all())


def voters_in_round(session: Session, estimation_round: EstimationRound) -> list[Member]:
    """The voters are the members who had joined when the round opened.

    For a re-estimation during a week, it is the members who had joined
    when the week opened (someone joining mid-week plays from next week).
    """
    cutoff = estimation_round.opened_at
    if estimation_round.week_id is not None:
        cutoff = session.get(Week, estimation_round.week_id).opened_at
    return list(
        session.exec(
            select(Member)
            .where(
                Member.household_id == estimation_round.household_id,
                Member.joined_at <= cutoff,
            )
            .order_by(Member.turn_order)
        ).all()
    )


def votes_in_round(session: Session, round_id: int) -> list[EffortVote]:
    return list(session.exec(select(EffortVote).where(EffortVote.round_id == round_id)).all())


def start_first_estimation(session: Session, household: Household) -> EstimationRound:
    if household.phase != Phase.SETUP:
        raise HTTPException(status_code=409, detail="Estimation can only start in SETUP")
    member_count = len(session.exec(select(Member).where(Member.household_id == household.id)).all())
    if member_count < MIN_MEMBERS_TO_ESTIMATE:
        raise HTTPException(status_code=409, detail="Estimation needs at least 2 members")
    chore_count = len(session.exec(select(Chore).where(Chore.household_id == household.id)).all())
    if chore_count == 0:
        raise HTTPException(status_code=409, detail="Estimation needs at least 1 chore")

    estimation_round = EstimationRound(household_id=household.id, opened_at=clock.now())
    session.add(estimation_round)
    household.phase = Phase.ESTIMATION
    session.commit()
    return estimation_round


def cast_vote(
    session: Session, household: Household, voter: Member, chore_id: int, points: int
) -> bool:
    """Record (or overwrite) a vote. Returns True if this vote closed the round."""
    estimation_round = require_open_round(session, household.id, lock=True)

    if voter.id not in {member.id for member in voters_in_round(session, estimation_round)}:
        raise HTTPException(status_code=403, detail="You joined after this estimation opened")
    if chore_id not in {chore.id for chore in chores_in_round(session, estimation_round)}:
        raise HTTPException(status_code=404, detail="Chore is not part of this estimation")

    # An "upsert": insert the vote, or if this person already voted on this
    # chore in this round (the unique constraint), update the points instead.
    statement = insert(EffortVote).values(
        round_id=estimation_round.id, chore_id=chore_id, member_id=voter.id, points=points
    )
    statement = statement.on_conflict_do_update(
        index_elements=["round_id", "chore_id", "member_id"],
        set_={"points": points},
    )
    session.execute(statement)

    closed = close_if_complete(session, household, estimation_round)
    session.commit()
    return closed


def close_if_complete(session: Session, household: Household, estimation_round: EstimationRound) -> bool:
    voter_ids = {member.id for member in voters_in_round(session, estimation_round)}
    chore_ids = {chore.id for chore in chores_in_round(session, estimation_round)}
    votes = {(vote.member_id, vote.chore_id) for vote in votes_in_round(session, estimation_round.id)}
    if not everyone_has_voted(voter_ids, chore_ids, votes):
        return False
    close_round(session, household, estimation_round, force=False)
    return True


def close_round(
    session: Session, household: Household, estimation_round: EstimationRound, force: bool
) -> EstimationResult:
    """Work out every chore's effort and close the round. Does not commit."""
    points_by_chore: dict[int, list[int]] = defaultdict(list)
    for vote in votes_in_round(session, estimation_round.id):
        points_by_chore[vote.chore_id].append(vote.points)

    chores = chores_in_round(session, estimation_round)
    unvoted = [chore.name for chore in chores if not points_by_chore[chore.id]]
    if unvoted:
        # Decision: force-closing is blocked while any chore has no votes at all.
        raise HTTPException(
            status_code=409,
            detail=f"These chores have no votes yet: {', '.join(unvoted)}",
        )

    efforts = []
    for chore in chores:
        votes = points_by_chore[chore.id]
        chore.effort_points = effort_from_votes(votes)
        efforts.append(ChoreEffort(chore_id=chore.id, effort_points=chore.effort_points, vote_count=len(votes)))
        if estimation_round.week_id is not None:
            # Re-estimation: the new value applies from this week, so update its snapshot too.
            week_chore = session.exec(
                select(WeekChore).where(
                    WeekChore.week_id == estimation_round.week_id, WeekChore.chore_id == chore.id
                )
            ).one()
            week_chore.effort_points = chore.effort_points

    estimation_round.closed_at = clock.now()
    estimation_round.force_closed = force
    if estimation_round.week_id is None:
        household.phase = Phase.ACTIVE

    return EstimationResult(
        round_id=estimation_round.id,
        closed_at=estimation_round.closed_at,
        force_closed=force,
        efforts=efforts,
    )


def force_close(session: Session, household: Household) -> EstimationResult:
    estimation_round = require_open_round(session, household.id, lock=True)
    result = close_round(session, household, estimation_round, force=True)
    session.commit()
    return result


def estimation_status(session: Session, household_id: int) -> EstimationStatus:
    estimation_round = require_open_round(session, household_id)
    voted: dict[int, list[int]] = defaultdict(list)
    for vote in votes_in_round(session, estimation_round.id):
        voted[vote.member_id].append(vote.chore_id)

    chore_ids = [chore.id for chore in chores_in_round(session, estimation_round)]
    voters = [
        VoterStatus(
            member_id=member.id,
            display_name=member.display_name,
            voted_chore_ids=sorted(voted[member.id]),
            done=set(voted[member.id]) >= set(chore_ids),
        )
        for member in voters_in_round(session, estimation_round)
    ]
    return EstimationStatus(
        round_id=estimation_round.id,
        week_id=estimation_round.week_id,
        opened_at=estimation_round.opened_at,
        chore_ids=chore_ids,
        voters=voters,
    )
