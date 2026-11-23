"""Shared test setup. pytest loads this file automatically."""

import pytest
from fastapi.testclient import TestClient

from app import storage
from app.main import app

OWNER = {"X-User-Email": "owner@example.com", "X-User-Name": "Olivia"}


@pytest.fixture(autouse=True)
def clear_storage():
    """Runs before every test, so no test sees another test's data."""
    storage.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def household(client: TestClient) -> dict:
    """A fresh household in SETUP, created by OWNER."""
    response = client.post("/households", json={"name": "Flat 4"}, headers=OWNER)
    return response.json()
