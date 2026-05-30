from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app.config import settings
from app.db import Base
import app.models  # noqa: F401 — registers all ORM models on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# inject the runtime DB URL so the alembic CLI works without an .env tweak
config.set_main_option("sqlalchemy.url", settings.db.url)

# render_as_batch is needed for SQLite (no ALTER COLUMN); harmful for Postgres
_BATCH = settings.db.url.startswith("sqlite")


def run_migrations_offline() -> None:
    context.configure(
        url=settings.db.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_BATCH,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    # NullPool — Alembic's connection has to close cleanly so it doesn't
    # collide with the app's own SQLite pool when both run in-process
    engine = create_engine(settings.db.url, poolclass=pool.NullPool)
    try:
        with engine.connect() as conn:
            context.configure(
                connection=conn,
                target_metadata=target_metadata,
                render_as_batch=_BATCH,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
