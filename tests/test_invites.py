from datetime import datetime, timedelta, timezone

from app.models import Phase
from tests.conftest import set_invite_expiry, set_phase
from tests.helpers import OWNER_EMAIL, as_user, join


def invite(client, household_id: int, email: str = "sam@example.com", by: str = OWNER_EMAIL):
    return client.post(f"/households/{household_id}/invites", json={"email": email}, headers=as_user(by))


def token_from(invite_response) -> str:
    # link looks like http://testserver/invites/<token>/accept
    return invite_response.json()["link"].split("/")[-2]


def test_create_invite_returns_201_with_link(client, household):
    response = invite(client, household["id"])

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "sam@example.com"
    assert "/invites/" in body["link"]


def test_invite_expires_in_7_days(client, household):
    body = invite(client, household["id"]).json()

    expires_at = datetime.fromisoformat(body["expires_at"])
    days_left = expires_at - datetime.now(timezone.utc)
    assert timedelta(days=6, hours=23) < days_left <= timedelta(days=7)


def test_invite_with_bad_email_returns_422(client, household):
    response = invite(client, household["id"], email="not-an-email")

    assert response.status_code == 422


def test_invite_with_unknown_field_returns_422(client, household):
    response = client.post(
        f"/households/{household['id']}/invites",
        json={"email": "sam@example.com", "role": "owner"},
        headers=as_user(OWNER_EMAIL),
    )

    assert response.status_code == 422


def test_invite_to_missing_household_returns_404(client, household):
    response = invite(client, 999)

    assert response.status_code == 404


def test_invite_during_estimation_returns_409(client, household):
    set_phase(household["id"], Phase.ESTIMATION)

    response = invite(client, household["id"])

    assert response.status_code == 409


def test_accept_invite_adds_member(client, household):
    token = token_from(invite(client, household["id"]))

    response = client.post(f"/invites/{token}/accept", headers={"X-User-Name": "Sam"})

    assert response.status_code == 201
    assert response.json()["display_name"] == "Sam"
    assert response.json()["turn_order"] == 2
    members = client.get(f"/households/{household['id']}", headers=as_user(OWNER_EMAIL)).json()["members"]
    assert len(members) == 2


def test_accept_with_bad_token_returns_404(client):
    response = client.post("/invites/nonsense/accept", headers={"X-User-Name": "Sam"})

    assert response.status_code == 404


def test_accept_twice_returns_410(client, household):
    token = token_from(invite(client, household["id"]))
    client.post(f"/invites/{token}/accept", headers={"X-User-Name": "Sam"})

    response = client.post(f"/invites/{token}/accept", headers={"X-User-Name": "Sam"})

    assert response.status_code == 410


def test_accept_expired_invite_returns_410(client, household):
    token = token_from(invite(client, household["id"]))
    set_invite_expiry(token, datetime.now(timezone.utc) - timedelta(seconds=1))

    response = client.post(f"/invites/{token}/accept", headers={"X-User-Name": "Sam"})

    assert response.status_code == 410


def test_accept_during_estimation_returns_409(client, household):
    token = token_from(invite(client, household["id"]))
    set_phase(household["id"], Phase.ESTIMATION)

    response = client.post(f"/invites/{token}/accept", headers={"X-User-Name": "Sam"})

    assert response.status_code == 409


def test_existing_member_cannot_join_again_returns_409(client, household):
    token = token_from(invite(client, household["id"], email="owner@example.com"))

    response = client.post(f"/invites/{token}/accept", headers={"X-User-Name": "Olivia"})

    assert response.status_code == 409


def test_only_the_owner_can_invite(client, household):
    join(client, household["id"], "sam@example.com", "Sam")

    response = invite(client, household["id"], "friend@example.com", by="sam@example.com")

    assert response.status_code == 403


def test_accepting_returns_the_new_member_s_api_key(client, household):
    token = token_from(invite(client, household["id"]))

    response = client.post(f"/invites/{token}/accept", headers={"X-User-Name": "Sam"})

    key = response.json()["api_key"]
    assert client.get(f"/households/{household['id']}", headers={"X-API-Key": key}).status_code == 200
