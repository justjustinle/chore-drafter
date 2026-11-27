"""Small API additions the browser front end relies on (Layer 11)."""

from tests.helpers import (
    ALEX_EMAIL,
    OWNER_EMAIL,
    SAM_EMAIL,
    as_user,
    auction_state,
    create_household,
    make_active_household,
    nominate,
    open_week,
    pass_turn,
    start_auction,
)


def test_me_says_who_the_key_belongs_to(client):
    household = create_household(client)

    me = client.get("/me", headers=as_user(OWNER_EMAIL)).json()

    assert me == {
        "member_id": household["owner_member_id"],
        "household_id": household["id"],
        "household_name": "Flat 4",
        "display_name": "Olivia",
        "is_owner": True,
    }


def test_household_shows_current_week_and_open_estimation(client):
    flat = make_active_household(client, {"Bins": 4})
    before = client.get(f"/households/{flat['id']}", headers=as_user(SAM_EMAIL)).json()
    assert before["current_week"] is None
    assert before["estimation_open"] is False

    week = open_week(client, flat["id"])
    client.post(f"/weeks/{week['id']}/flags", json={"chore_id": flat["chores"]["Bins"]}, headers=as_user(SAM_EMAIL))
    client.post(f"/weeks/{week['id']}/estimation/start", headers=as_user(OWNER_EMAIL))

    after = client.get(f"/households/{flat['id']}", headers=as_user(SAM_EMAIL)).json()
    assert after["current_week"]["id"] == week["id"]
    assert after["current_week"]["status"] == "OPEN"
    assert after["estimation_open"] is True
    week_now = client.get(f"/weeks/{week['id']}", headers=as_user(SAM_EMAIL)).json()
    assert week_now["flagged_chore_ids"] == [flat["chores"]["Bins"]]


def test_auction_state_lists_passes_sold_chores_and_server_time(client):
    flat = make_active_household(client, {"Bins": 4, "Hoover": 6})
    week = open_week(client, flat["id"])
    start_auction(client, week["id"])
    nominate(client, week["id"], OWNER_EMAIL, flat["chores"]["Bins"], 3, turn_number=1)
    pass_turn(client, week["id"], SAM_EMAIL, turn_number=1)

    state = auction_state(client, week["id"])
    assert state["lot"]["passed_member_ids"] == [flat["sam"]]
    assert "server_time" in state

    pass_turn(client, week["id"], ALEX_EMAIL, turn_number=2)
    state = auction_state(client, week["id"])
    assert [c["name"] for c in state["sold_chores"]] == ["Bins"]
    assert [c["name"] for c in state["unsold_chores"]] == ["Hoover"]


def test_cors_allows_the_front_end(client):
    response = client.options(
        "/households",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
