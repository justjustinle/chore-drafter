import threading

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import AuctionAction
from tests.helpers import (
    ALEX_EMAIL,
    OWNER_EMAIL,
    SAM_EMAIL,
    auction_state,
    bid,
    make_active_household,
    nominate,
    open_week,
    pass_turn,
    start_auction,
)

EFFORTS = {"Bins": 4, "Hoover": 6, "Dishes": 2}


@pytest.fixture
def game(client):
    """Owner, Sam and Alex (turn order 1, 2, 3) in a week whose auction has started."""
    flat = make_active_household(client, EFFORTS)
    week = open_week(client, flat["id"])
    start_auction(client, week["id"])
    return {**flat, "week": week["id"]}


def test_first_nominator_is_the_first_member(client, game):
    state = auction_state(client, game["week"])

    assert state["status"] == "AUCTION"
    assert state["nomination"]["member_id"] == game["owner"]
    assert state["nomination"]["turn_number"] == 1


def test_only_the_nominator_can_nominate(client, game):
    response = nominate(client, game["week"], SAM_EMAIL, game["chores"]["Bins"], 5, turn_number=1)

    assert response.status_code == 403


def test_stale_turn_number_is_rejected(client, game):
    response = nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=99)

    assert response.status_code == 409


def test_a_full_lot(client, game):
    bins = game["chores"]["Bins"]

    state = nominate(client, game["week"], OWNER_EMAIL, bins, 5, turn_number=1).json()
    assert state["lot"]["turn_member_id"] == game["sam"]  # bidding starts after the nominator
    assert state["lot"]["turn_number"] == 1

    state = bid(client, game["week"], SAM_EMAIL, 7, turn_number=1).json()
    assert state["lot"]["high_bidder_id"] == game["sam"]
    assert state["lot"]["turn_member_id"] == game["alex"]

    state = pass_turn(client, game["week"], ALEX_EMAIL, turn_number=2).json()
    assert state["lot"]["turn_member_id"] == game["owner"]

    state = pass_turn(client, game["week"], OWNER_EMAIL, turn_number=3).json()

    # Sold to Sam for 7. Everyone got +1 when Bins was nominated.
    assert state["lot"] is None
    tokens = {m["member_id"]: m["tokens_left"] for m in state["members"]}
    assert tokens == {game["owner"]: 101, game["sam"]: 94, game["alex"]: 101}
    # The next nominator is the member after the previous nominator.
    assert state["nomination"]["member_id"] == game["sam"]
    assert state["nomination"]["turn_number"] == 2
    assert [c["name"] for c in state["unsold_chores"]] == ["Hoover", "Dishes"]


def test_bid_must_beat_the_high_bid(client, game):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)

    assert bid(client, game["week"], SAM_EMAIL, 5, turn_number=1).status_code == 409


def test_bid_cannot_exceed_the_budget(client, game):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)

    assert bid(client, game["week"], SAM_EMAIL, 102, turn_number=1).status_code == 409


def test_not_your_turn_to_bid(client, game):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)

    assert bid(client, game["week"], ALEX_EMAIL, 6, turn_number=1).status_code == 403


def test_members_who_cannot_beat_the_bid_pass_automatically(client, game):
    # The owner has 100 + 1 = 101 tokens and opens at all of them. Nobody
    # else can bid 102, so they pass automatically and the chore sells at once.
    state = nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 101, turn_number=1).json()

    assert state["lot"] is None
    tokens = {m["member_id"]: m["tokens_left"] for m in state["members"]}
    assert tokens[game["owner"]] == 0
    assert state["nomination"]["member_id"] == game["sam"]


def test_nominator_always_has_a_token_to_open_with(client, game):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 101, turn_number=1)  # owner: 0 left
    nominate(client, game["week"], SAM_EMAIL, game["chores"]["Hoover"], 1, turn_number=2)
    pass_turn(client, game["week"], ALEX_EMAIL, turn_number=1)
    # The owner has 0 + 1 (from Hoover) = 1 token, can only match, so auto-passes. Sam wins.

    state = auction_state(client, game["week"])
    assert state["nomination"]["member_id"] == game["alex"]
    response = nominate(client, game["week"], ALEX_EMAIL, game["chores"]["Dishes"], 1, turn_number=3)
    assert response.status_code == 200


def test_timeout_counts_as_a_pass(client, game, fake_clock):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)

    fake_clock.advance(31)  # Sam does nothing for 31 seconds
    state = auction_state(client, game["week"])

    assert state["lot"]["turn_member_id"] == game["alex"]
    assert state["lot"]["turn_number"] == 2
    with Session(engine) as session:
        timed_out = session.exec(select(AuctionAction).where(AuctionAction.timed_out)).all()
    assert [(a.member_id, a.turn_number) for a in timed_out] == [(game["sam"], 1)]


def test_late_action_is_rejected_after_timeout(client, game, fake_clock):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)
    fake_clock.advance(31)

    response = bid(client, game["week"], SAM_EMAIL, 6, turn_number=1)

    assert response.status_code == 409  # turn 1 is over; it is Alex's turn 2 now


def test_missed_nomination_turns_are_skipped(client, game, fake_clock):
    fake_clock.advance(65)  # two whole turns go by, and part of a third

    state = auction_state(client, game["week"])

    assert state["nomination"]["member_id"] == game["alex"]
    assert state["nomination"]["turn_number"] == 3


def test_auction_ends_when_every_chore_is_sold(client, game):
    week = game["week"]
    for turn, (email, chore) in enumerate(
        [(OWNER_EMAIL, "Bins"), (SAM_EMAIL, "Hoover"), (ALEX_EMAIL, "Dishes")], start=1
    ):
        nominate(client, week, email, game["chores"][chore], 1, turn_number=turn)
        state = auction_state(client, week)
        while state["lot"] is not None:
            turn_email = {game["owner"]: OWNER_EMAIL, game["sam"]: SAM_EMAIL, game["alex"]: ALEX_EMAIL}[
                state["lot"]["turn_member_id"]
            ]
            pass_turn(client, week, turn_email, state["lot"]["turn_number"])
            state = auction_state(client, week)

    assert state["status"] == "ASSIGNED"
    assert state["unsold_chores"] == []
    assert {m["member_id"]: m["effort_won"] for m in state["members"]} == {
        game["owner"]: 4,
        game["sam"]: 6,
        game["alex"]: 2,
    }


def test_two_bids_for_the_same_turn_at_once_exactly_one_wins(game):
    """Sam double-taps: two bids for turn 1 arrive at the same moment."""
    week = game["week"]
    first = TestClient(app)
    nominate(first, week, OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)

    start_line = threading.Barrier(2)
    results = []

    def send_bid(amount):
        client = TestClient(app)  # each thread uses its own client and database session
        start_line.wait()  # both threads go at exactly the same time
        results.append(bid(client, week, SAM_EMAIL, amount, turn_number=1).status_code)

    threads = [threading.Thread(target=send_bid, args=(amount,)) for amount in (10, 11)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [200, 409]
    with Session(engine) as session:
        turn_one = session.exec(
            select(AuctionAction).where(AuctionAction.turn_number == 1, AuctionAction.kind == "BID")
        ).all()
    assert len(turn_one) == 1
