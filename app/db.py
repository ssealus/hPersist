from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_is_sqlite = settings.db.url.startswith("sqlite")

engine = create_engine(
    settings.db.url,
    echo=settings.db.echo,
    future=True,
    pool_size=settings.db.pool_size,
    max_overflow=settings.db.max_overflow,
    pool_timeout=settings.db.pool_timeout_seconds,
    pool_recycle=settings.db.pool_recycle_seconds,
    connect_args=(
        {
            "check_same_thread": False,
            "timeout": settings.db.sqlite_busy_timeout_ms / 1000,
        }
        if _is_sqlite
        else {}
    ),
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):  # noqa: ANN001
    if not _is_sqlite:
        return
    cur = dbapi_conn.cursor()
    cur.execute(f"PRAGMA journal_mode={settings.db.sqlite_journal_mode}")
    cur.execute(f"PRAGMA foreign_keys={'ON' if settings.db.sqlite_foreign_keys else 'OFF'}")
    cur.execute(f"PRAGMA synchronous={settings.db.sqlite_synchronous}")
    cur.execute(f"PRAGMA busy_timeout={settings.db.sqlite_busy_timeout_ms}")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency. Commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
