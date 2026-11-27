import pytest

from tests.helpers import OWNER_EMAIL, add_chore, as_user, create_household, invite_token, join, vote

SAM = "sam@example.com"


@pytest.fixture
def flat(client):
    """A household in SETUP with the owner, Sam, and two chores."""
    household = create_household(client)
    join(client, household["id"], SAM, "Sam")
    bins = add_chore(client, household["id"], "Bins")
    hoover = add_chore(client, household["id"], "Hoover")
    return {"id": household["id"], "bins": bins["id"], "hoover": hoover["id"]}


def start(client, household_id, email=OWNER_EMAIL):
    return client.post(f"/households/{household_id}/estimation/start", headers=as_user(email))


def test_start_moves_household_to_estimation(client, flat):
    response = start(client, flat["id"])

    assert response.status_code == 201
    assert client.get(f"/households/{flat['id']}", headers=as_user(SAM)).json()["phase"] == "ESTIMATION"


def test_only_owner_can_start(client, flat):
    assert start(client, flat["id"], email=SAM).status_code == 403


def test_start_needs_two_members(client):
    household = create_household(client)
    add_chore(client, household["id"], "Bins")

    assert start(client, household["id"]).status_code == 409


def test_start_needs_a_chore(client):
    household = create_household(client)
    join(client, household["id"], SAM, "Sam")

    assert start(client, household["id"]).status_code == 409


def test_cannot_start_twice(client, flat):
    start(client, flat["id"])

    assert start(client, flat["id"]).status_code == 409


def test_vote_outside_estimation_returns_409(client, flat):
    assert vote(client, flat["id"], flat["bins"], 5, OWNER_EMAIL).status_code == 409


def test_vote_out_of_range_returns_422(client, flat):
    start(client, flat["id"])

    assert vote(client, flat["id"], flat["bins"], 11, OWNER_EMAIL).status_code == 422
    assert vote(client, flat["id"], flat["bins"], 0, OWNER_EMAIL).status_code == 422


def test_non_member_cannot_vote(client, flat):
    start(client, flat["id"])
    create_household(client, "stranger@example.com", "Stranger")  # a real key, for another household

    assert vote(client, flat["id"], flat["bins"], 5, "stranger@example.com").status_code == 403


def test_vote_without_a_key_returns_401(client, flat):
    start(client, flat["id"])

    assert vote(client, flat["id"], flat["bins"], 5, "nobody@example.com").status_code == 401


def test_vote_on_unknown_chore_returns_404(client, flat):
    start(client, flat["id"])

    assert vote(client, flat["id"], 999, 5, OWNER_EMAIL).status_code == 404


def test_status_shows_who_voted_but_never_the_values(client, flat):
    start(client, flat["id"])
    vote(client, flat["id"], flat["bins"], 7, OWNER_EMAIL)

    response = client.get(f"/households/{flat['id']}/estimation", headers=as_user(SAM))

    assert response.status_code == 200
    owner, sam = response.json()["voters"]
    assert owner["voted_chore_ids"] == [flat["bins"]]
    assert owner["done"] is False
    assert sam["voted_chore_ids"] == []
    assert "points" not in response.text  # no vote values anywhere in the response


def test_revote_overwrites(client, flat):
    start(client, flat["id"])
    vote(client, flat["id"], flat["bins"], 2, OWNER_EMAIL)
    vote(client, flat["id"], flat["bins"], 9, OWNER_EMAIL)  # changes their mind
    vote(client, flat["id"], flat["hoover"], 1, OWNER_EMAIL)
    vote(client, flat["id"], flat["bins"], 9, SAM)
    vote(client, flat["id"], flat["hoover"], 1, SAM)

    chores = client.get(f"/households/{flat['id']}/chores", headers=as_user(SAM)).json()
    assert chores[0]["effort_points"] == 9  # (9 + 9) / 2, not (2 + 9) / 2


def test_auto_closes_when_everyone_has_voted(client, flat):
    start(client, flat["id"])
    vote(client, flat["id"], flat["bins"], 4, OWNER_EMAIL)
    vote(client, flat["id"], flat["hoover"], 6, OWNER_EMAIL)
    vote(client, flat["id"], flat["bins"], 5, SAM)

    last = vote(client, flat["id"], flat["hoover"], 6, SAM)

    assert last.json()["estimation_closed"] is True
    household = client.get(f"/households/{flat['id']}", headers=as_user(SAM)).json()
    assert household["phase"] == "ACTIVE"
    efforts = {c["id"]: c["effort_points"] for c in household["chores"]}
    assert efforts == {flat["bins"]: 5, flat["hoover"]: 6}  # 4.5 rounds up to 5


def test_values_stay_hidden_until_close(client, flat):
    start(client, flat["id"])
    vote(client, flat["id"], flat["bins"], 4, OWNER_EMAIL)

    chores = client.get(f"/households/{flat['id']}/chores", headers=as_user(SAM)).json()
    assert all(c["effort_points"] is None for c in chores)


def test_force_close_ignores_missing_votes(client, flat):
    start(client, flat["id"])
    vote(client, flat["id"], flat["bins"], 3, OWNER_EMAIL)
    vote(client, flat["id"], flat["hoover"], 8, SAM)  # Sam never votes on bins

    response = client.post(f"/households/{flat['id']}/estimation/close", headers=as_user(OWNER_EMAIL))

    assert response.status_code == 200
    assert response.json()["force_closed"] is True
    efforts = {e["chore_id"]: e["effort_points"] for e in response.json()["efforts"]}
    assert efforts == {flat["bins"]: 3, flat["hoover"]: 8}


def test_force_close_blocked_while_a_chore_has_no_votes(client, flat):
    start(client, flat["id"])
    vote(client, flat["id"], flat["bins"], 3, OWNER_EMAIL)

    response = client.post(f"/households/{flat['id']}/estimation/close", headers=as_user(OWNER_EMAIL))

    assert response.status_code == 409
    assert "Hoover" in response.json()["detail"]


def test_only_owner_can_force_close(client, flat):
    start(client, flat["id"])

    response = client.post(f"/households/{flat['id']}/estimation/close", headers=as_user(SAM))

    assert response.status_code == 403


def test_cannot_accept_invite_during_estimation(client, flat):
    token = invite_token(client, flat["id"], "late@example.com")
    start(client, flat["id"])

    response = client.post(f"/invites/{token}/accept", headers={"X-User-Name": "Late"})

    assert response.status_code == 409
