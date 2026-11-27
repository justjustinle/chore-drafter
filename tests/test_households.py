from sqlmodel import Session, select

from app.db import engine
from app.models import Phase, User
from tests.conftest import OWNER
from tests.helpers import OWNER_EMAIL, as_user


def test_create_household_returns_201_and_starts_in_setup(client):
    response = client.post("/households", json={"name": "Flat 4"}, headers=OWNER)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Flat 4"
    assert body["phase"] == Phase.SETUP
    assert body["chores"] == []


def test_creator_becomes_owner_and_first_member(client):
    body = client.post("/households", json={"name": "Flat 4"}, headers=OWNER).json()

    assert len(body["members"]) == 1
    owner = body["members"][0]
    assert owner["email"] == "owner@example.com"
    assert owner["display_name"] == "Olivia"
    assert owner["turn_order"] == 1
    assert body["owner_member_id"] == owner["id"]


def test_client_cannot_choose_phase_returns_422(client):
    response = client.post(
        "/households", json={"name": "Flat 4", "phase": "ACTIVE"}, headers=OWNER
    )

    assert response.status_code == 422


def test_create_household_with_empty_name_returns_422(client):
    response = client.post("/households", json={"name": ""}, headers=OWNER)

    assert response.status_code == 422


def test_create_household_without_identity_headers_returns_422(client):
    response = client.post("/households", json={"name": "Flat 4"})

    assert response.status_code == 422


def test_get_household(client, household):
    response = client.get(f"/households/{household['id']}", headers=as_user(OWNER_EMAIL))

    assert response.status_code == 200
    assert response.json()["name"] == "Flat 4"


def test_get_missing_household_returns_404(client, household):
    response = client.get("/households/999", headers=as_user(OWNER_EMAIL))

    assert response.status_code == 404


def test_database_is_empty_at_start_of_each_test(client):
    # If the reset fixture did not run, households from earlier tests would exist.
    # Any key at all would mean a member exists, so 401 proves the tables are empty.
    assert client.get("/households/1", headers=as_user(OWNER_EMAIL)).status_code == 401


def test_same_person_in_two_households_is_one_user(client):
    first = client.post("/households", json={"name": "Flat 4"}, headers=OWNER).json()
    second = client.post("/households", json={"name": "Holiday home"}, headers=OWNER).json()

    # Two separate memberships...
    assert first["members"][0]["id"] != second["members"][0]["id"]
    # ...belonging to one user row.
    with Session(engine) as session:
        users = session.exec(select(User)).all()
    assert len(users) == 1


def test_creating_a_household_returns_the_owner_s_api_key_once(client, household):
    assert household["api_key"].startswith("cd_")
    again = client.get(f"/households/{household['id']}", headers={"X-API-Key": household["api_key"]})
    assert "api_key" not in again.json()  # never shown again


def test_get_household_with_a_wrong_key_returns_401(client, household):
    response = client.get(f"/households/{household['id']}", headers={"X-API-Key": "cd_made_up"})

    assert response.status_code == 401


def test_database_health_check_reports_the_migration(client):
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"database": "ok", "migration": "0004"}
