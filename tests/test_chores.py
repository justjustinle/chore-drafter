from app.models import Phase
from tests.conftest import set_phase
from tests.helpers import OWNER_EMAIL, as_user, create_household


def add_chore(client, household_id: int, json: dict, headers: dict | None = None):
    headers = headers if headers is not None else as_user(OWNER_EMAIL)
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


def test_add_chore_with_missing_name_returns_422(client, household):
    response = add_chore(client, household["id"], {"description": "no name"})

    assert response.status_code == 422


def test_add_chore_with_unknown_field_returns_422(client, household):
    response = add_chore(client, household["id"], {"name": "Bins", "colur": "green"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "colur"]


def test_add_chore_to_missing_household_returns_404(client, household):
    response = add_chore(client, 999, {"name": "Bins"})

    assert response.status_code == 404


def test_add_chore_outside_setup_returns_409(client, household):
    set_phase(household["id"], Phase.ACTIVE)

    response = add_chore(client, household["id"], {"name": "Bins"})

    assert response.status_code == 409


def test_member_of_another_household_cannot_add_chore_returns_403(client, household):
    create_household(client, "stranger@example.com", "Stranger")  # has a valid key, for a different household

    response = add_chore(client, household["id"], {"name": "Bins"}, headers=as_user("stranger@example.com"))

    assert response.status_code == 403


def test_add_chore_without_a_key_returns_401(client, household):
    response = add_chore(client, household["id"], {"name": "Bins"}, headers={})

    assert response.status_code == 401


def test_list_chores_only_shows_this_household(client, household):
    other = create_household(client, "x@example.com", "X")
    add_chore(client, household["id"], {"name": "Bins"})
    add_chore(client, household["id"], {"name": "Hoover"})
    add_chore(client, other["id"], {"name": "Dishes"}, headers=as_user("x@example.com"))

    response = client.get(f"/households/{household['id']}/chores", headers=as_user(OWNER_EMAIL))

    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Bins", "Hoover"]


def test_list_chores_for_missing_household_returns_404(client, household):
    response = client.get("/households/999/chores", headers=as_user(OWNER_EMAIL))

    assert response.status_code == 404
