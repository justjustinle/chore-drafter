"""The database connection.

DATABASE_URL says which database to use. The default matches
docker-compose.yml, so locally you do not need to set anything.
In production (Vercel + Neon) DATABASE_URL is set in the project settings.
"""

import os
from collections.abc import Iterator

from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine

DEFAULT_URL = "postgresql+psycopg://chore:chore@localhost:5432/chore_draft"


def normalise_url(url: str) -> str:
    """Hosted providers hand out "postgres://..." or "postgresql://..." URLs.
    SQLAlchemy needs to be told which driver to use, so make it
    "postgresql+psycopg://..." (psycopg 3, the driver in requirements.txt)."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = normalise_url(os.environ.get("DATABASE_URL", DEFAULT_URL))

# Vercel sets VERCEL=1. There, each request may run in a fresh, short-lived
# function, so keeping a pool of open connections is pointless; connect per
# request instead, and let the provider's pooler (Neon's "-pooler" host)
# share connections between functions.
SERVERLESS = os.environ.get("VERCEL") == "1"

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool if SERVERLESS else None,
    pool_pre_ping=not SERVERLESS,  # check a pooled connection is still alive before using it
    # Poolers like PgBouncer (behind Neon's pooled URL) cannot keep prepared
    # statements between transactions, so tell psycopg not to make them.
    connect_args={"prepare_threshold": None},
)


def get_session() -> Iterator[Session]:
    """Give each request its own session, and close it when the request ends.

    Endpoints ask for one with:  session: Session = Depends(get_session)
    """
    with Session(engine) as session:
        yield session
