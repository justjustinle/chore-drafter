"""The database connection.

DATABASE_URL says which database to use. The default matches
docker-compose.yml, so locally you do not need to set anything.
"""

import os
from collections.abc import Iterator

from sqlmodel import Session, create_engine

DEFAULT_URL = "postgresql+psycopg://chore:chore@localhost:5432/chore_draft"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_URL)

# The engine manages connections to Postgres. Create it once and share it.
engine = create_engine(DATABASE_URL)


def get_session() -> Iterator[Session]:
    """Give each request its own session, and close it when the request ends.

    Endpoints ask for one with:  session: Session = Depends(get_session)
    """
    with Session(engine) as session:
        yield session
