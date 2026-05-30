"""ORM models.

The shape mirrors the result envelope described in the schema doc. A
collection run produces an :class:`Inventory` with a list of :class:`Server`
records; each server holds normalized component sub-rows plus a JSON blob with
the raw Redfish payload for deep dives.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


class Inventory(Base):
    __tablename__ = "inventories"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: _uid("inv"))
    name: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    mode: Mapped[str] = mapped_column(String(32))         # local | smart-hands
    submode: Mapped[str] = mapped_column(String(32))      # cidr | csv | script | process

    status: Mapped[str] = mapped_column(String(32), default="in-progress")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None]
    duration_seconds: Mapped[float | None]

    created_by: Mapped[str | None] = mapped_column(String(200))
    collector_version: Mapped[str | None] = mapped_column(String(40))
    script_sha256: Mapped[str | None] = mapped_column(String(64))
    integrity_seed: Mapped[str | None] = mapped_column(String(64))
    integrity_status: Mapped[str | None] = mapped_column(String(32))
    integrity_notes: Mapped[str | None] = mapped_column(Text)

    servers: Mapped[list["Server"]] = relationship(
        back_populates="inventory", cascade="all, delete-orphan"
    )
    job: Mapped["CollectionJob | None"] = relationship(
        back_populates="inventory", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def reached(self) -> int:
        return sum(1 for s in self.servers if s.collection_status == "ok")

    @property
    def failed(self) -> int:
        return sum(1 for s in self.servers if s.collection_status == "failed")


class Server(Base):
    __tablename__ = "servers"
    __table_args__ = (UniqueConstraint("inventory_id", "serial_number", name="uq_inv_sn"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: _uid("srv"))
    inventory_id: Mapped[str] = mapped_column(ForeignKey("inventories.id", ondelete="CASCADE"), index=True)

    ilo_ip: Mapped[str | None] = mapped_column(String(64))
    hostname: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(64), index=True)
    sku: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(120))
    manufacturer: Mapped[str | None] = mapped_column(String(80))
    form_factor: Mapped[str | None] = mapped_column(String(80))
    generation: Mapped[str | None] = mapped_column(String(32))

    ilo_generation: Mapped[str | None] = mapped_column(String(16))   # iLO 4/5/6
    ilo_firmware: Mapped[str | None] = mapped_column(String(40))
    bios_version: Mapped[str | None] = mapped_column(String(64))

    power_state: Mapped[str | None] = mapped_column(String(16))
    health: Mapped[str | None] = mapped_column(String(16))

    total_memory_gb: Mapped[float | None]
    total_storage_gb: Mapped[float | None]

    collection_status: Mapped[str] = mapped_column(String(16), default="ok")
    collection_error: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None]
    collected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    inventory: Mapped[Inventory] = relationship(back_populates="servers")
    components: Mapped[list["Component"]] = relationship(
        back_populates="server", cascade="all, delete-orphan"
    )


class Component(Base):
    """A single hardware item — CPU, DIMM, drive, NIC, PSU, mainboard, etc."""

    __tablename__ = "components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)

    group: Mapped[str] = mapped_column(String(40), index=True)        # CPU/DIMM/Drive/NIC/PSU/System
    label: Mapped[str] = mapped_column(String(255))                   # human-readable spec
    part_number: Mapped[str | None] = mapped_column(String(64), index=True)
    serial_number: Mapped[str | None] = mapped_column(String(64))
    location: Mapped[str | None] = mapped_column(String(120))         # socket/slot/bay
    manufacturer: Mapped[str | None] = mapped_column(String(80))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    capacity_value: Mapped[float | None] = mapped_column(Float)       # GB / W / GHz, see capacity_unit
    capacity_unit: Mapped[str | None] = mapped_column(String(16))
    firmware_version: Mapped[str | None] = mapped_column(String(40))
    health: Mapped[str | None] = mapped_column(String(16))
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    server: Mapped[Server] = relationship(back_populates="components")


class CollectionJob(Base):
    __tablename__ = "collection_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: _uid("job"))
    inventory_id: Mapped[str] = mapped_column(
        ForeignKey("inventories.id", ondelete="CASCADE"), unique=True, index=True
    )

    state: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|failed|cancelled
    total_hosts: Mapped[int] = mapped_column(default=0)
    completed: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)

    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    log_path: Mapped[str | None] = mapped_column(String(400))

    inventory: Mapped[Inventory] = relationship(back_populates="job")


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventory_id: Mapped[str | None] = mapped_column(ForeignKey("inventories.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    level: Mapped[str] = mapped_column(String(8))
    host: Mapped[str | None] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)


class TelemetryEvent(Base):
    """Anonymized usage / timing events. No SN / IP / hostnames here."""

    __tablename__ = "telemetry_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)        # collection.start | host.timing | error
    mode: Mapped[str | None] = mapped_column(String(40))
    duration_ms: Mapped[int | None]
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class UserSetting(Base):
    """Persistent key-value store for UI preferences (locale, theme, density, …)."""

    __tablename__ = "user_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class RedfishProbeHistory(Base):
    """Ad-hoc Redfish tester request log.

    Stores the request shape (host, port, method, path, username, tls, body)
    and the response status + RTT so the UI can show recent probes and the
    user can click a row to re-populate the form. Passwords and response
    bodies are deliberately NOT persisted.
    """

    __tablename__ = "redfish_probe_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=443)
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(500))
    username: Mapped[str | None] = mapped_column(String(200))
    tls: Mapped[str] = mapped_column(String(16), default="warn-only")
    request_body: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
