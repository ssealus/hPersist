"""Collector base class and registry.

Drop a new module into ``app/redfish/collectors/`` exposing a subclass of
:class:`BaseCollector` and add it to ``COLLECTORS`` (see ``__init__`` for the
default chain). The walker invokes every collector against the same fetched
top-level resources, accumulating normalised :class:`Component` rows plus a
free-form ``raw`` dict per collector.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.redfish.client import RedfishClient


@dataclass(slots=True)
class ComponentRow:
    """Normalized component row, mirrors :class:`app.models.Component`."""

    group: str
    label: str
    part_number: str | None = None
    serial_number: str | None = None
    location: str | None = None
    manufacturer: str | None = None
    quantity: int = 1
    capacity_value: float | None = None
    capacity_unit: str | None = None
    firmware_version: str | None = None
    health: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CollectorResult:
    """Output of one collector run against one host."""

    components: list[ComponentRow] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)


class BaseCollector:
    """Override :meth:`collect`. Must not raise — wrap own exceptions."""

    name: str = "base"

    async def collect(
        self,
        client: RedfishClient,
        system: dict,
        chassis: dict,
        manager: dict,
    ) -> CollectorResult:
        raise NotImplementedError


def safe_get(d: dict, *path, default=None):
    """Walk a path of dict keys; return ``default`` if any segment is missing."""
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur
