from sqlmodel import Session, select

from app.db import engine
from app.models import Chore
from tests.helpers import (
    ALEX_EMAIL,
    OWNER_EMAIL,
    SAM_EMAIL,
    as_user,
    create_household,
    join,
    make_active_household,
    open_week,
    vote,
)

EFFORTS = {"Bins": 4, "Hoover": 6}


def test_open_week_snapshots_effort(client):
    flat = make_active_household(client, EFFORTS)

    week = open_week(client, flat["id"])

    assert week["status"] == "OPEN"
    assert {c["name"]: c["effort_points"] for c in week["chores"]} == EFFORTS


def test_snapshot_keeps_its_value_when_the_chore_changes(client):
    flat = make_active_household(client, EFFORTS)
    week = open_week(client, flat["id"])
    with Session(engine) as session:
        chore = session.get(Chore, flat["chores"]["Bins"])
        chore.effort_points = 9
        session.commit()

    week_now = client.get(f"/weeks/{week['id']}", headers=as_user(OWNER_EMAIL)).json()

    assert {c["name"]: c["effort_points"] for c in week_now["chores"]}["Bins"] == 4


def test_cannot_open_a_week_before_estimation(client):
    household = create_household(client)

    response = client.post(f"/households/{household['id']}/weeks", json={}, headers=as_user(OWNER_EMAIL))

    assert response.status_code == 409


def test_only_one_unclosed_week_at_a_time(client):
    flat = make_active_household(client, EFFORTS)
    open_week(client, flat["id"], "2026-11-29")

    response = client.post(
        f"/households/{flat['id']}/weeks", json={"starts_on": "2026-12-06"}, headers=as_user(OWNER_EMAIL)
    )

    assert response.status_code == 409


def flag(client, week_id, chore_id, email):
    return client.post(f"/weeks/{week_id}/flags", json={"chore_id": chore_id}, headers=as_user(email))


def test_flagging_twice_is_harmless(client):
    flat = make_active_household(client, EFFORTS)
    week = open_week(client, flat["id"])

    flag(client, week["id"], flat["chores"]["Bins"], SAM_EMAIL)
    response = flag(client, week["id"], flat["chores"]["Bins"], SAM_EMAIL)

    assert response.status_code == 200
    assert response.json()["flagged_chore_ids"] == [flat["chores"]["Bins"]]


def test_auction_waits_for_flagged_chores_to_be_re_estimated(client):
    flat = make_active_household(client, EFFORTS)
    week = open_week(client, flat["id"])
    flag(client, week["id"], flat["chores"]["Bins"], SAM_EMAIL)

    response = client.post(f"/weeks/{week['id']}/auction/start", headers=as_user(OWNER_EMAIL))

    assert response.status_code == 409


def test_re_estimation_updates_this_week_and_the_chore(client):
    flat = make_active_household(client, EFFORTS)
    week = open_week(client, flat["id"])
    bins = flat["chores"]["Bins"]
    flag(client, week["id"], bins, SAM_EMAIL)

    started = client.post(f"/weeks/{week['id']}/estimation/start", headers=as_user(OWNER_EMAIL))
    assert started.status_code == 201
    assert started.json()["chore_ids"] == [bins]  # only the flagged chore
    for email, points in [(OWNER_EMAIL, 7), (SAM_EMAIL, 8), (ALEX_EMAIL, 8)]:
        vote(client, flat["id"], bins, points, email)

    week_now = client.get(f"/weeks/{week['id']}", headers=as_user(OWNER_EMAIL)).json()
    assert {c["name"]: c["effort_points"] for c in week_now["chores"]}["Bins"] == 8  # 7.67 rounds up
    response = client.post(f"/weeks/{week['id']}/auction/start", headers=as_user(OWNER_EMAIL))
    assert response.status_code == 200


def test_member_who_joins_mid_week_plays_next_week(client):
    flat = make_active_household(client, EFFORTS)
    week = open_week(client, flat["id"])
    join(client, flat["id"], "late@example.com", "Late")

    response = flag(client, week["id"], flat["chores"]["Bins"], "late@example.com")

    assert response.status_code == 403
