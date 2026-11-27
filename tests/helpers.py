"""Small helpers that build test data through the real API."""

from fastapi.testclient import TestClient

OWNER_EMAIL = "owner@example.com"


def as_user(email: str) -> dict:
    """Headers that make a request come from this person."""
    return {"X-User-Email": email}


def create_household(client: TestClient, email: str = OWNER_EMAIL, name: str = "Olivia") -> dict:
    response = client.post(
        "/households",
        json={"name": "Flat 4"},
        headers={"X-User-Email": email, "X-User-Name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def join(client: TestClient, household_id: int, email: str, name: str) -> dict:
    """Invite someone and have them accept. Returns their member."""
    invite = client.post(f"/households/{household_id}/invites", json={"email": email})
    token = invite.json()["link"].split("/")[-2]
    response = client.post(f"/invites/{token}/accept", headers={"X-User-Name": name})
    assert response.status_code == 201, response.text
    return response.json()


def add_chore(client: TestClient, household_id: int, name: str, email: str = OWNER_EMAIL) -> dict:
    response = client.post(
        f"/households/{household_id}/chores", json={"name": name}, headers=as_user(email)
    )
    assert response.status_code == 201, response.text
    return response.json()


def vote(client: TestClient, household_id: int, chore_id: int, points: int, email: str):
    return client.put(
        f"/households/{household_id}/estimation/votes/{chore_id}",
        json={"points": points},
        headers=as_user(email),
    )
