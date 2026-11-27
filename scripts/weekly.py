"""The weekly scheduled job.

A plain Python script, run on a timer (cron, or an Azure Container Apps job
in Layer 10). It reuses exactly the same service functions as the API, so
the rules live in one place.

    python -m scripts.weekly open-week          # Sunday: close last week, open this one, send the reminder
    python -m scripts.weekly finish-unfinished  # Monday: assign anything the ceremony left unsold

Both commands are safe to run twice: every step checks the current state
first and does nothing if it is already done.
"""

import argparse
import logging
from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, select

from app import clock
from app.db import engine
from app.models import Household, Member, Phase, Week, WeekStatus
from app.services import results, weeks

log = logging.getLogger("weekly")


def send_reminder(household: Household, members: list[Member]) -> None:
    """Until email exists (Layer 12), the reminder is a log line."""
    names = ", ".join(member.display_name for member in members)
    log.info("Reminder for %s: the chore auction is tonight. Players: %s", household.name, names)


def active_households(session: Session) -> list[Household]:
    return list(session.exec(select(Household).where(Household.phase == Phase.ACTIVE)).all())


def unclosed_week(session: Session, household_id: int) -> Week | None:
    week = session.exec(
        select(Week).where(Week.household_id == household_id, Week.status != WeekStatus.CLOSED)
    ).first()
    if week is None:
        return None
    return weeks.get_week_or_404(session, week.id, lock=True)


def finish_unfinished(session: Session, today: date) -> list[int]:
    """Assign the chores of any earlier week whose ceremony did not finish.

    Returns the ids of the weeks it finished.
    """
    finished = []
    for household in active_households(session):
        week = unclosed_week(session, household.id)
        if week is None or week.starts_on >= today:
            continue  # nothing to do, or this week's ceremony may still be running
        if week.status in (WeekStatus.OPEN, WeekStatus.AUCTION):
            results.finish(session, household, week)  # idempotent
            finished.append(week.id)
            log.info("Finished week %s for %s", week.id, household.name)
    return finished


def open_this_week(session: Session, today: date) -> list[int]:
    """Close last week (finishing it first if needed) and open this week.

    Returns the ids of the weeks it opened.
    """
    opened = []
    for household in active_households(session):
        week = unclosed_week(session, household.id)
        if week is not None:
            if week.starts_on == today:
                continue  # already opened today: a second run does nothing
            results.finish(session, household, week)  # no-op if already ASSIGNED
            results.close_week(session, week)  # no-op if already CLOSED
            log.info("Closed week %s for %s", week.id, household.name)

        already = session.exec(
            select(Week).where(Week.household_id == household.id, Week.starts_on == today)
        ).first()
        if already is not None:
            continue
        try:
            new_week = weeks.open_week(session, household, today)
        except HTTPException as error:  # the same rule checks the API uses
            log.warning("Could not open a week for %s: %s", household.name, error.detail)
            session.rollback()
            continue
        opened.append(new_week.id)
        send_reminder(household, weeks.week_members(session, new_week))
    return opened


def main() -> None:
    parser = argparse.ArgumentParser(description="Chore Draft weekly job")
    parser.add_argument("command", choices=["open-week", "finish-unfinished"])
    parser.add_argument("--date", type=date.fromisoformat, help="pretend today is this date (YYYY-MM-DD)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    today = args.date or clock.now().date()
    with Session(engine) as session:
        if args.command == "open-week":
            ids = open_this_week(session, today)
            log.info("Opened %d week(s)", len(ids))
        else:
            ids = finish_unfinished(session, today)
            log.info("Finished %d week(s)", len(ids))


if __name__ == "__main__":
    main()
