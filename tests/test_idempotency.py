import threading

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.main import app
from app.models import AuctionAction, AuctionLot
from tests.helpers import (
    OWNER_EMAIL,
    SAM_EMAIL,
    as_user,
    make_active_household,
    nominate,
    open_week,
    start_auction,
)

EFFORTS = {"Bins": 4, "Hoover": 6}


@pytest.fixture
def game(client):
    flat = make_active_household(client, EFFORTS)
    week = open_week(client, flat["id"])
    start_auction(client, week["id"])
    return {**flat, "week": week["id"]}


def bid_with_key(client, week_id, amount, turn_number, key, email=SAM_EMAIL):
    return client.post(
        f"/weeks/{week_id}/auction/bid",
        json={"amount": amount, "turn_number": turn_number},
        headers={**as_user(email), "Idempotency-Key": key},
    )


def bids_recorded(amount):
    with Session(engine) as session:
        return len(
            session.exec(select(AuctionAction).where(AuctionAction.kind == "BID", AuctionAction.amount == amount)).all()
        )


def test_a_repeated_key_returns_the_original_response(client, game):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)

    first = bid_with_key(client, game["week"], 7, 1, key="retry-123")
    retry = bid_with_key(client, game["week"], 7, 1, key="retry-123")

    assert first.status_code == retry.status_code == 200
    assert retry.json() == first.json()
    assert bids_recorded(7) == 1  # acted once


def test_without_a_key_the_retry_is_a_stale_turn(client, game):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)
    url = f"/weeks/{game['week']}/auction/bid"
    body = {"amount": 7, "turn_number": 1}

    client.post(url, json=body, headers=as_user(SAM_EMAIL))
    retry = client.post(url, json=body, headers=as_user(SAM_EMAIL))

    assert retry.status_code == 409  # this is the confusing error the key avoids


def test_replay_returns_the_original_even_after_the_auction_moved_on(client, game):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)
    first = bid_with_key(client, game["week"], 7, 1, key="k1")
    client.post(  # Alex passes: the auction moves on
        f"/weeks/{game['week']}/auction/pass", json={"turn_number": 2}, headers=as_user("alex@example.com")
    )

    retry = bid_with_key(client, game["week"], 7, 1, key="k1")

    assert retry.json() == first.json()


def test_same_key_on_a_different_endpoint_is_rejected(client, game):
    nominate(client, game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)
    bid_with_key(client, game["week"], 7, 1, key="k1")

    response = client.post(
        f"/weeks/{game['week']}/auction/pass",
        json={"turn_number": 2},
        headers={**as_user(SAM_EMAIL), "Idempotency-Key": "k1"},
    )

    assert response.status_code == 422


def test_keys_belong_to_one_member(client, game):
    # The owner nominates with key "k1"; Sam using "k1" too is a different key.
    client.post(
        f"/weeks/{game['week']}/auction/nominate",
        json={"chore_id": game["chores"]["Bins"], "opening_bid": 5, "turn_number": 1},
        headers={**as_user(OWNER_EMAIL), "Idempotency-Key": "k1"},
    )

    response = bid_with_key(client, game["week"], 7, 1, key="k1")

    assert response.status_code == 200
    assert response.json()["lot"]["high_bidder_id"] == game["sam"]


def test_nominate_retry_does_not_open_a_second_lot(client, game):
    body = {"chore_id": game["chores"]["Bins"], "opening_bid": 5, "turn_number": 1}
    headers = {**as_user(OWNER_EMAIL), "Idempotency-Key": "nominate-1"}

    first = client.post(f"/weeks/{game['week']}/auction/nominate", json=body, headers=headers)
    retry = client.post(f"/weeks/{game['week']}/auction/nominate", json=body, headers=headers)

    assert retry.json() == first.json()
    with Session(engine) as session:
        assert len(session.exec(select(AuctionLot)).all()) == 1


def test_two_identical_retries_at_once_act_once(game):
    nominate(TestClient(app), game["week"], OWNER_EMAIL, game["chores"]["Bins"], 5, turn_number=1)
    start_line = threading.Barrier(2)
    responses = []

    def send():
        client = TestClient(app)
        start_line.wait()
        responses.append(bid_with_key(client, game["week"], 7, 1, key="same-key"))

    threads = [threading.Thread(target=send) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert bids_recorded(7) == 1
