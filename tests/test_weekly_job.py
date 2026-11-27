import logging
from datetime import date

from sqlmodel import Session, select

from app.db import engine
from app.models import Week
from scripts.weekly import finish_unfinished, open_this_week
from tests.helpers import (
    OWNER_EMAIL,
    as_user,
    make_active_household,
    nominate,
    open_week,
    start_auction,
)

EFFORTS = {"Bins": 4, "Hoover": 6}
SUNDAY = date(2026, 11, 29)
MONDAY = date(2026, 11, 30)
NEXT_SUNDAY = date(2026, 12, 6)


def weeks_of(household_id):
    with Session(engine) as session:
        rows = session.exec(select(Week).where(Week.household_id == household_id).order_by(Week.starts_on)).all()
        return [(w.starts_on, w.status) for w in rows]


def run(job, today):
    with Session(engine) as session:
        return job(session, today)


def test_open_week_opens_one_week_and_is_safe_to_run_twice(client, caplog):
    caplog.set_level(logging.INFO, logger="weekly")
    flat = make_active_household(client, EFFORTS)

    first = run(open_this_week, SUNDAY)
    second = run(open_this_week, SUNDAY)

    assert len(first) == 1
    assert second == []
    assert weeks_of(flat["id"]) == [(SUNDAY, "OPEN")]
    assert "chore auction is tonight" in caplog.text


def test_finish_unfinished_assigns_an_abandoned_ceremony(client):
    flat = make_active_household(client, EFFORTS)
    week = open_week(client, flat["id"], SUNDAY.isoformat())
    start_auction(client, week["id"])
    nominate(client, week["id"], OWNER_EMAIL, flat["chores"]["Bins"], 3, turn_number=1)
    # ...and then everybody went to bed.

    finished = run(finish_unfinished, MONDAY)
    again = run(finish_unfinished, MONDAY)

    assert finished == [week["id"]]
    assert again == []  # safe to run twice
    assignments = client.get(f"/weeks/{week['id']}/assignments", headers=as_user(OWNER_EMAIL)).json()
    assert all(c["assigned_member_id"] is not None for c in assignments["chores"])


def test_finish_unfinished_leaves_todays_ceremony_alone(client):
    flat = make_active_household(client, EFFORTS)
    open_week(client, flat["id"], SUNDAY.isoformat())

    assert run(finish_unfinished, SUNDAY) == []
    assert weeks_of(flat["id"]) == [(SUNDAY, "OPEN")]


def test_next_sunday_closes_last_week_and_opens_a_new_one(client):
    flat = make_active_household(client, EFFORTS)
    run(open_this_week, SUNDAY)  # the ceremony never happens

    run(open_this_week, NEXT_SUNDAY)
    run(open_this_week, NEXT_SUNDAY)  # and a second run changes nothing

    assert weeks_of(flat["id"]) == [(SUNDAY, "CLOSED"), (NEXT_SUNDAY, "OPEN")]


def test_households_still_in_setup_are_skipped(client):
    client.post("/households", json={"name": "New"}, headers={"X-User-Email": "a@b.com", "X-User-Name": "A"})

    assert run(open_this_week, SUNDAY) == []
