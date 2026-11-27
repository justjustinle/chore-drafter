"""The database connection.

DATABASE_URL says which database the app uses; DATABASE_URL_UNPOOLED (if
set) is the direct connection that migrations use.

- On Vercel, both are set in the project's environment variables.
- On your PC, `neon env pull` writes both into `.env.local`, which is loaded
  below. Without that file the app uses the local Docker database.

Variables already set in the environment always win over the files.
"""

import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for env_file in (".env.local", ".env"):
    load_dotenv(PROJECT_ROOT / env_file, override=False)

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

# Migrations need a direct connection: Neon's pooled URL goes through
# PgBouncer in transaction mode, which breaks session-level steps.
MIGRATION_URL = normalise_url(os.environ.get("DATABASE_URL_UNPOOLED", DATABASE_URL))

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
