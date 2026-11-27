"""The Vercel entry point serves the same API under /api."""

from fastapi.testclient import TestClient

from api.index import app as vercel_app


def test_api_is_served_under_api_prefix():
    client = TestClient(vercel_app)

    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.post(
        "/api/households",
        json={"name": "Flat 4"},
        headers={"X-User-Email": "a@example.com", "X-User-Name": "A"},
    )
    assert response.status_code == 201
