"""Logging utilities.

Each collection run gets its own logger. Lines are written to a file inside
``$HPERSIST_DATA_DIR/logs/`` and also persisted to the ``log_entries`` table so
the UI can display them later. The file is exportable as-is for support /
troubleshooting.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from app.config import settings
from app.db import session_scope
from app.models import LogEntry

_LOCK = threading.Lock()
_LOGGERS: dict[str, "InventoryLogger"] = {}


class InventoryLogger:
    """Lightweight per-inventory logger.

    Not a stdlib ``logging.Logger`` — keeping it small lets us push the same
    line to the file, to sqlite, and to the WebSocket subscribers in one call.
    """

    def __init__(self, inventory_id: str) -> None:
        self.inventory_id = inventory_id
        self.path: Path = settings.data_dir / "logs" / f"{inventory_id}.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")
        self._subscribers: list[callable] = []

    def subscribe(self, fn) -> None:
        self._subscribers.append(fn)

    def unsubscribe(self, fn) -> None:
        if fn in self._subscribers:
            self._subscribers.remove(fn)

    def log(self, level: str, message: str, host: str | None = None) -> dict:
        ts = datetime.utcnow()
        line = f"{ts.isoformat(timespec='milliseconds')} {level.upper():<5} {host or '-':<22} {message}"
        with _LOCK:
            self._fh.write(line + "\n")
            self._fh.flush()
        try:
            # fresh connection — caller probably holds an open session_scope
            from sqlalchemy import insert
            from app.db import engine
            with engine.begin() as conn:
                conn.execute(
                    insert(LogEntry).values(
                        inventory_id=self.inventory_id,
                        ts=ts,
                        level=level.lower(),
                        host=host,
                        message=message,
                    )
                )
        except Exception:  # pragma: no cover — never let logging break a run
            logging.getLogger("hpersist").debug("log persist failed", exc_info=True)
        evt = {"ts": ts.isoformat(timespec="milliseconds"), "level": level.lower(), "host": host, "message": message}
        for sub in list(self._subscribers):
            try:
                sub(evt)
            except Exception:
                pass
        return evt

    def info(self, msg: str, host: str | None = None) -> dict: return self.log("info", msg, host)
    def ok(self, msg: str, host: str | None = None) -> dict: return self.log("ok", msg, host)
    def warn(self, msg: str, host: str | None = None) -> dict: return self.log("warn", msg, host)
    def err(self, msg: str, host: str | None = None) -> dict: return self.log("err", msg, host)

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass


def get_logger(inventory_id: str) -> InventoryLogger:
    with _LOCK:
        lg = _LOGGERS.get(inventory_id)
        if lg is None:
            lg = InventoryLogger(inventory_id)
            _LOGGERS[inventory_id] = lg
        return lg


def stream_log_lines(inventory_id: str, level: str | None = None) -> Iterator[dict]:
    """Replay the persisted log entries for an inventory."""
    from sqlalchemy import select

    with session_scope() as s:
        q = select(LogEntry).where(LogEntry.inventory_id == inventory_id).order_by(LogEntry.ts)
        if level:
            q = q.where(LogEntry.level == level)
        for row in s.scalars(q):
            yield {"ts": row.ts.isoformat(timespec="milliseconds"), "level": row.level, "host": row.host, "message": row.message}


def prune_old_logs(days: int | None = None) -> int:
    """Remove file logs older than ``days`` and matching DB rows. Returns count."""
    from datetime import timedelta

    from sqlalchemy import delete

    cutoff = datetime.utcnow() - timedelta(days=days or settings.log.retention_days)
    count = 0
    for p in (settings.data_dir / "logs").glob("*.log"):
        if datetime.utcfromtimestamp(p.stat().st_mtime) < cutoff:
            p.unlink(missing_ok=True)
            count += 1
    with session_scope() as s:
        s.execute(delete(LogEntry).where(LogEntry.ts < cutoff))
    return count


def export_lines(inventory_id: str) -> Iterable[str]:
    p = settings.data_dir / "logs" / f"{inventory_id}.log"
    if p.exists():
        yield from p.read_text(encoding="utf-8").splitlines(keepends=True)
