"""Alembic migration parity — `alembic upgrade head` must build the same schema
that `Base.metadata.create_all` builds. Catches the classic "added a column,
forgot the migration" bug.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

REPO_ROOT = Path(__file__).resolve().parent.parent


def _schema_snapshot(engine) -> dict:
    """Return {table_name: sorted(column_names)} for comparison."""
    insp = inspect(engine)
    return {
        t: sorted(c["name"] for c in insp.get_columns(t))
        for t in insp.get_table_names()
        if t != "alembic_version"  # alembic adds this; not in metadata
    }


def test_alembic_upgrade_head_matches_metadata(tmp_path: Path):
    db = tmp_path / "alembic-check.db"
    url = f"sqlite:///{db}"

    # 1. Run alembic upgrade head against an empty SQLite — exercises every migration.
    env_override = {"HPERSIST_DB__URL": url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, **env_override},
    )
    assert result.returncode == 0, f"alembic failed:\n{result.stderr}"

    # 2. Build a second DB straight from Base.metadata.
    other_db = tmp_path / "metadata-check.db"
    other_url = f"sqlite:///{other_db}"
    import app.models  # noqa: F401 — register tables
    from app.db import Base

    other_engine = create_engine(other_url)
    Base.metadata.create_all(other_engine)

    # 3. Compare table+column sets.
    migrated = _schema_snapshot(create_engine(url))
    metadata = _schema_snapshot(other_engine)

    assert migrated == metadata, (
        f"Schema drift:\n"
        f"  only in migrations: {set(migrated) - set(metadata)}\n"
        f"  only in metadata:   {set(metadata) - set(migrated)}\n"
        f"  column diffs:       {[t for t in migrated if t in metadata and migrated[t] != metadata[t]]}"
    )
