"""Shared test setup. pytest loads this file automatically.

The tests run against a real Postgres database, chore_draft_test, which is
separate from the dev database so running the tests never touches dev data.
"""

import os

# Point the app at the test database. This must happen before anything
# imports app.db, because that is where the engine is created.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://chore:chore@localhost:5432/chore_draft_test"
)

from datetime import datetime  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlmodel import Session, SQLModel, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Household, Invite, Phase  # noqa: E402

OWNER = {"X-User-Email": "owner@example.com", "X-User-Name": "Olivia"}


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Once per test run: rebuild the schema from scratch using the migrations.

    This also proves the migrations work on an empty database.
    """
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clear_tables():
    """Before every test: empty every table and restart the ids at 1."""
    table_names = ", ".join(f'"{table.name}"' for table in SQLModel.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def household(client: TestClient) -> dict:
    """A fresh household in SETUP, created by OWNER."""
    response = client.post("/households", json={"name": "Flat 4"}, headers=OWNER)
    return response.json()


# Shortcuts for tests that need a state the API cannot reach yet
# (estimation arrives in Layer 3).

def set_phase(household_id: int, phase: Phase) -> None:
    with Session(engine) as session:
        household = session.get(Household, household_id)
        household.phase = phase
        session.commit()


def set_invite_expiry(token: str, expires_at: datetime) -> None:
    with Session(engine) as session:
        invite = session.exec(select(Invite).where(Invite.token == token)).one()
        invite.expires_at = expires_at
        session.commit()
