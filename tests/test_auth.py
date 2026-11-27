"""Layer 8: API keys. Members act only as themselves; owner-only actions are enforced."""

import pytest
from sqlmodel import Session, select

from app.db import engine
from app.identity import hash_key
from app.models import Member
from tests.helpers import (
    KEYS,
    OWNER_EMAIL,
    SAM_EMAIL,
    add_chore,
    as_user,
    create_household,
    finish,
    join,
    make_active_household,
    open_week,
    start_auction,
)


def test_the_database_stores_only_a_hash_of_the_key(client):
    household = create_household(client)
    key = household["api_key"]

    with Session(engine) as session:
        owner = session.get(Member, household["owner_member_id"])

    assert owner.api_key_hash == hash_key(key)
    assert key not in owner.api_key_hash


def test_every_member_gets_a_different_key(client):
    household = create_household(client)
    join(client, household["id"], SAM_EMAIL, "Sam")

    assert KEYS[OWNER_EMAIL] != KEYS[SAM_EMAIL]


def test_a_key_works_only_for_its_own_household(client):
    """The same person in two households has two keys; each opens one door."""
    first = create_household(client, OWNER_EMAIL, "Olivia")
    first_key = KEYS[OWNER_EMAIL]
    second = create_household(client, OWNER_EMAIL, "Olivia")

    response = client.get(f"/households/{second['id']}", headers={"X-API-Key": first_key})

    assert response.status_code == 403
    assert client.get(f"/households/{first['id']}", headers={"X-API-Key": first_key}).status_code == 200


def test_a_member_cannot_act_as_someone_else(client):
    """Sam cannot add a chore credited to the owner: the key decides who you are."""
    household = create_household(client)
    join(client, household["id"], SAM_EMAIL, "Sam")

    chore = add_chore(client, household["id"], "Bins", email=SAM_EMAIL)

    with Session(engine) as session:
        sam = session.exec(select(Member).where(Member.display_name == "Sam")).one()
    assert chore["created_by"] == sam.id


@pytest.fixture
def week_in_auction(client):
    flat = make_active_household(client, {"Bins": 4, "Hoover": 6})
    week = open_week(client, flat["id"])
    start_auction(client, week["id"])
    return {**flat, "week": week["id"]}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/households/{household}/invites"),
        ("post", "/households/{household}/estimation/close"),
        ("post", "/weeks/{week}/finish"),
        ("post", "/weeks/{week}/close"),
    ],
)
def test_owner_only_actions_return_403_for_other_members(client, week_in_auction, method, path):
    url = path.format(household=week_in_auction["id"], week=week_in_auction["week"])
    body = {"email": "friend@example.com"} if "invites" in path else None

    response = getattr(client, method)(url, json=body, headers=as_user(SAM_EMAIL))

    assert response.status_code == 403


def test_bidding_on_someone_else_s_turn_returns_403(client, week_in_auction):
    client.post(
        f"/weeks/{week_in_auction['week']}/auction/nominate",
        json={"chore_id": week_in_auction["chores"]["Bins"], "opening_bid": 3, "turn_number": 1},
        headers=as_user(OWNER_EMAIL),
    )

    # It is Sam's turn; Alex tries to bid with Alex's own key.
    response = client.post(
        f"/weeks/{week_in_auction['week']}/auction/bid",
        json={"amount": 5, "turn_number": 1},
        headers=as_user("alex@example.com"),
    )

    assert response.status_code == 403


def test_marking_someone_else_s_chore_done_returns_403(client, week_in_auction):
    body = finish(client, week_in_auction["week"]).json()
    owners_chore = next(c for c in body["chores"] if c["assigned_member_id"] == week_in_auction["owner"])

    response = client.post(f"/week-chores/{owners_chore['id']}/done", headers=as_user(SAM_EMAIL))

    assert response.status_code == 403


def test_no_key_returns_401(client, week_in_auction):
    assert client.get(f"/weeks/{week_in_auction['week']}/auction").status_code == 401
