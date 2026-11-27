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


ALEX_EMAIL = "alex@example.com"
SAM_EMAIL = "sam@example.com"


def make_active_household(client: TestClient, efforts: dict[str, int]) -> dict:
    """Owner, Sam and Alex, with the given chores already estimated.

    Everyone votes the same number, so each chore's effort is exactly the
    number given. Returns ids for the household, members and chores.
    """
    household = create_household(client)
    sam = join(client, household["id"], SAM_EMAIL, "Sam")
    alex = join(client, household["id"], ALEX_EMAIL, "Alex")
    chores = {name: add_chore(client, household["id"], name)["id"] for name in efforts}
    response = client.post(f"/households/{household['id']}/estimation/start", headers=as_user(OWNER_EMAIL))
    assert response.status_code == 201, response.text
    for email in (OWNER_EMAIL, SAM_EMAIL, ALEX_EMAIL):
        for name, points in efforts.items():
            vote(client, household["id"], chores[name], points, email)
    return {
        "id": household["id"],
        "owner": household["owner_member_id"],
        "sam": sam["id"],
        "alex": alex["id"],
        "chores": chores,
    }


def open_week(client: TestClient, household_id: int, starts_on: str = "2026-11-29") -> dict:
    response = client.post(
        f"/households/{household_id}/weeks", json={"starts_on": starts_on}, headers=as_user(OWNER_EMAIL)
    )
    assert response.status_code == 201, response.text
    return response.json()


def start_auction(client: TestClient, week_id: int) -> dict:
    response = client.post(f"/weeks/{week_id}/auction/start", headers=as_user(OWNER_EMAIL))
    assert response.status_code == 200, response.text
    return response.json()


def auction_state(client: TestClient, week_id: int, email: str = OWNER_EMAIL) -> dict:
    return client.get(f"/weeks/{week_id}/auction", headers=as_user(email)).json()


def nominate(client, week_id: int, email: str, chore_id: int, opening_bid: int, turn_number: int):
    return client.post(
        f"/weeks/{week_id}/auction/nominate",
        json={"chore_id": chore_id, "opening_bid": opening_bid, "turn_number": turn_number},
        headers=as_user(email),
    )


def bid(client, week_id: int, email: str, amount: int, turn_number: int):
    return client.post(
        f"/weeks/{week_id}/auction/bid",
        json={"amount": amount, "turn_number": turn_number},
        headers=as_user(email),
    )


def pass_turn(client, week_id: int, email: str, turn_number: int):
    return client.post(
        f"/weeks/{week_id}/auction/pass", json={"turn_number": turn_number}, headers=as_user(email)
    )
