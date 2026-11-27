import pytest
from sqlmodel import Session

from app.db import engine
from app.models import Chore
from tests.helpers import (
    ALEX_EMAIL,
    OWNER_EMAIL,
    SAM_EMAIL,
    as_user,
    auction_state,
    bid,
    close_week,
    finish,
    make_active_household,
    nominate,
    open_week,
    start_auction,
)

EFFORTS = {"Bins": 4, "Hoover": 6, "Dishes": 2, "Bathroom": 8}


@pytest.fixture
def game(client):
    flat = make_active_household(client, EFFORTS)
    week = open_week(client, flat["id"])
    start_auction(client, week["id"])
    return {**flat, "week": week["id"]}


def effort_by_member(assignments):
    return {m["member_id"]: m["effort"] for m in assignments["members"]}


def test_finish_with_no_bids_shares_out_evenly(client, game):
    response = finish(client, game["week"])

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ASSIGNED"
    assert all(c["assigned_via"] == "FINISH" for c in body["chores"])
    # Bathroom 8 -> owner, Hoover 6 -> Sam, Bins 4 -> Alex, Dishes 2 -> Alex (lowest on 4).
    assert effort_by_member(body) == {game["owner"]: 8, game["sam"]: 6, game["alex"]: 6}


def test_finish_takes_auction_wins_into_account(client, game):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bathroom"], 1, turn_number=1)
    bid(client, game["week"], SAM_EMAIL, 2, turn_number=1)  # Sam now leads on Bathroom

    body = finish(client, game["week"]).json()

    by_name = {c["name"]: c for c in body["chores"]}
    # The chore mid-auction goes to the high bidder at their bid.
    assert by_name["Bathroom"]["assigned_member_id"] == game["sam"]
    assert by_name["Bathroom"]["assigned_via"] == "AUCTION"
    assert by_name["Bathroom"]["price_paid"] == 2
    # Sam already has 8, so the leftovers go to the other two.
    assert effort_by_member(body)[game["sam"]] == 8


def test_running_finish_twice_changes_nothing(client, game):
    first = finish(client, game["week"]).json()

    second = finish(client, game["week"])

    assert second.status_code == 200
    assert second.json() == first


def test_only_owner_can_finish(client, game):
    assert finish(client, game["week"], SAM_EMAIL).status_code == 403


def test_assignments_before_finishing_returns_409(client, game):
    response = client.get(f"/weeks/{game['week']}/assignments", headers=as_user(SAM_EMAIL))

    assert response.status_code == 409


def test_only_the_assigned_member_can_mark_done(client, game):
    body = finish(client, game["week"]).json()
    bathroom = next(c for c in body["chores"] if c["name"] == "Bathroom")  # the owner's

    assert client.post(f"/week-chores/{bathroom['id']}/done", headers=as_user(SAM_EMAIL)).status_code == 403
    response = client.post(f"/week-chores/{bathroom['id']}/done", headers=as_user(OWNER_EMAIL))
    assert response.status_code == 200
    assert response.json()["done_at"] is not None


def test_cannot_mark_done_before_assignment(client, game):
    state = auction_state(client, game["week"])
    any_chore = state["unsold_chores"][0]["id"]

    response = client.post(f"/week-chores/{any_chore}/done", headers=as_user(OWNER_EMAIL))

    assert response.status_code == 409


def test_close_week_and_history_keep_the_week_s_effort(client, game):
    finish(client, game["week"])
    assert close_week(client, game["week"]).status_code == 200
    assert close_week(client, game["week"]).status_code == 200  # closing twice is harmless
    with Session(engine) as session:  # Bins is re-estimated to 9 afterwards
        session.get(Chore, game["chores"]["Bins"]).effort_points = 9
        session.commit()

    history = client.get(f"/households/{game['id']}/history", headers=as_user(ALEX_EMAIL)).json()

    assert len(history) == 1
    bins = next(c for c in history[0]["chores"] if c["name"] == "Bins")
    assert bins["effort_points"] == 4  # the snapshot from that week, not today's 9
    assert bins["assigned_to"] == "Alex"


def test_cannot_close_before_finishing(client, game):
    assert close_week(client, game["week"]).status_code == 409


def test_first_nominator_rotates_to_the_next_member_next_week(client, game):
    finish(client, game["week"])
    close_week(client, game["week"])
    next_week = open_week(client, game["id"], "2026-12-06")

    state = start_auction(client, next_week["id"])

    assert state["nomination"]["member_id"] == game["sam"]
