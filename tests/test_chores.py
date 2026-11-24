from app import storage
from app.schemas import Phase
from tests.conftest import OWNER


def add_chore(client, household_id: int, json: dict, headers: dict = OWNER):
    return client.post(f"/households/{household_id}/chores", json=json, headers=headers)


def test_add_chore_returns_201(client, household):
    response = add_chore(client, household["id"], {"name": "Bins", "description": "Tuesday night"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Bins"
    assert body["description"] == "Tuesday night"
    assert body["effort_points"] is None
    assert body["created_by"] == household["owner_member_id"]


def test_description_is_optional(client, household):
    response = add_chore(client, household["id"], {"name": "Bins"})

    assert response.status_code == 201
    assert response.json()["description"] is None


def test_colour_is_optional(client, household):
    response = add_chore(client, household["id"], {"name": "Bins"})

    assert response.status_code == 201
    assert response.json()["colour"] is None


def test_colour_is_saved_when_given(client, household):
    response = add_chore(client, household["id"], {"name": "Bins", "colour": "green"})

    assert response.status_code == 201
    assert response.json()["colour"] == "green"


def test_add_chore_with_missing_name_returns_422(client, household):
    response = add_chore(client, household["id"], {"description": "no name"})

    assert response.status_code == 422


def test_add_chore_to_missing_household_returns_404(client):
    response = add_chore(client, 999, {"name": "Bins"})

    assert response.status_code == 404


def test_add_chore_outside_setup_returns_409(client, household):
    storage.households[household["id"]].phase = Phase.ACTIVE

    response = add_chore(client, household["id"], {"name": "Bins"})

    assert response.status_code == 409


def test_non_member_cannot_add_chore_returns_403(client, household):
    stranger = {"X-User-Email": "stranger@example.com"}

    response = add_chore(client, household["id"], {"name": "Bins"}, headers=stranger)

    assert response.status_code == 403


def test_list_chores_only_shows_this_household(client, household):
    other = client.post(
        "/households", json={"name": "Other flat"},
        headers={"X-User-Email": "x@example.com", "X-User-Name": "X"},
    ).json()
    add_chore(client, household["id"], {"name": "Bins"})
    add_chore(client, household["id"], {"name": "Hoover"})
    add_chore(client, other["id"], {"name": "Dishes"},
              headers={"X-User-Email": "x@example.com"})

    response = client.get(f"/households/{household['id']}/chores")

    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Bins", "Hoover"]


def test_list_chores_for_missing_household_returns_404(client):
    response = client.get("/households/999/chores")

    assert response.status_code == 404
