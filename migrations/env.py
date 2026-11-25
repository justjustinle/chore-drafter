"""Alembic runs this file for every migration command.

It connects to DATABASE_URL (see app/db.py) and compares the database
with the tables defined in app/models.py.
"""

from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

from app import models  # noqa: F401  (importing registers every table on SQLModel.metadata)
from app.db import engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Write the SQL to the screen instead of running it (alembic upgrade --sql)."""
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
