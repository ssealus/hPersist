"""Local telemetry rollups.

`anonymized_export` is the one safe to share with maintainers: only counts,
buckets and catalog identifiers (model names, manufacturer PNs). No
hostnames, IPs, MACs, serials, orgs, descriptions, raw Redfish payloads or
credentials ever appear in the output.
"""
from __future__ import annotations

import platform
import sys
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.models import Component, Inventory, Server, TelemetryEvent


def rollup(session: Session, *, window_days: int = 30) -> dict[str, Any]:
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    runs = session.scalars(select(Inventory).where(Inventory.created_at >= cutoff)).all()
    servers_touched = sum(len(i.servers) for i in runs)
    timings = [int((s.duration_seconds or 0) * 1000) for i in runs for s in i.servers if s.duration_seconds]
    timings.sort()
    percentiles = _percentiles(timings, [10, 50, 90, 99])

    modes = Counter(f"{i.mode}.{i.submode}" for i in runs)
    errors = Counter(_classify_error(s.collection_error) for i in runs for s in i.servers if s.collection_error)
    ilo_mix = Counter(s.ilo_generation or "unknown" for i in runs for s in i.servers if s.ilo_generation)
    models = Counter(s.model or "unknown" for i in runs for s in i.servers if s.model)

    series = _daily_series(runs, window_days)

    return {
        "version": __version__,
        "schema": "telemetry/anon-v1",
        "window_days": window_days,
        "runs": len(runs),
        "servers_touched": servers_touched,
        "modes": dict(modes),
        "timing_ms": percentiles,
        "errors": dict(errors),
        "ilo_mix": dict(ilo_mix),
        "model_mix": dict(models),
        "daily_runs": series,
    }


def storage_footprint(session: Session) -> dict[str, Any]:
    from app.config import settings as _settings

    db_path = (_settings.data_dir / "hpersist.db")
    size = db_path.stat().st_size if db_path.exists() else 0
    logs_size = sum(p.stat().st_size for p in (_settings.data_dir / "logs").glob("*.log") if p.is_file())
    archives_size = sum(p.stat().st_size for p in (_settings.data_dir / "archives").glob("*") if p.is_file())
    inv_rows = session.scalar(select(func.count(Inventory.id)))
    srv_rows = session.scalar(select(func.count(Server.id)))
    return {
        "db_bytes": size,
        "logs_bytes": logs_size,
        "archives_bytes": archives_size,
        "inventories": int(inv_rows or 0),
        "servers": int(srv_rows or 0),
    }


_CORE_BUCKETS = [0, 8, 16, 32, 64, 128, 256]
_MEM_BUCKETS_GB = [0, 32, 64, 128, 256, 512, 1024, 2048]
_STORAGE_BUCKETS_GB = [0, 500, 1000, 2000, 5000, 10000, 20000, 50000]
_PSU_BUCKETS_W = [0, 500, 1000, 2000, 4000, 8000, 16000]
_TOP_PN_LIMIT = 20


def _bucket_label(value: float | int, edges: list[int]) -> str:
    """Return a human-friendly bucket label for ``value`` against the given edges."""
    v = int(value or 0)
    for i in range(len(edges) - 1):
        if edges[i] <= v < edges[i + 1]:
            return f"{edges[i]}-{edges[i + 1] - 1}"
    return f"{edges[-1]}+"


def _per_collector_timing(events: list[TelemetryEvent]) -> dict[str, dict[str, int]]:
    # per-collector timings stay on the host record's `timings` field and never
    # reach telemetry_events. only host-total duration is recoverable here.
    by_collector: dict[str, list[int]] = {}
    for ev in events:
        if ev.kind != "host.timing":
            continue
        by_collector.setdefault("host_total", []).append(ev.duration_ms or 0)
    out = {}
    for k, vals in by_collector.items():
        vals.sort()
        out[k] = _percentiles(vals, [50, 90, 99]) if vals else {"p50": 0, "p90": 0, "p99": 0}
    return out


def _per_mode_duration(runs: list[Inventory]) -> dict[str, dict[str, int]]:
    by_mode: dict[str, list[int]] = {}
    for inv in runs:
        if inv.duration_seconds is None:
            continue
        key = f"{inv.mode}.{inv.submode}"
        by_mode.setdefault(key, []).append(int(inv.duration_seconds * 1000))
    out = {}
    for k, vals in by_mode.items():
        vals.sort()
        out[k] = _percentiles(vals, [50, 90, 99]) if vals else {"p50": 0, "p90": 0, "p99": 0}
    return out


def _component_stats(servers: list[Server]) -> dict[str, Any]:
    group_counts: Counter[str] = Counter()
    pn_counts: Counter[str] = Counter()
    dimm_speed: Counter[str] = Counter()
    dimm_type: Counter[str] = Counter()
    drive_label: Counter[str] = Counter()
    psu_watts: Counter[int] = Counter()
    nic_speeds: Counter[str] = Counter()

    for s in servers:
        for c in s.components:
            group_counts[c.group] += c.quantity or 1
            if c.part_number:
                pn_counts[c.part_number.strip()] += c.quantity or 1
            extra = c.extra or {}
            if c.group == "DIMM":
                # `extra` can hold PII (Port has MAC/IPv4 in there) — only touch
                # named keys, never iterate the whole dict.
                speed = extra.get("speed_mts") or extra.get("speed_mhz") or extra.get("OperatingSpeedMhz")
                if speed:
                    dimm_speed[str(speed)] += 1
                mtype = extra.get("type") or extra.get("memory_type") or extra.get("MemoryType")
                if mtype:
                    dimm_type[str(mtype)] += 1
            elif c.group == "Drive" and c.label:
                # bucket by media type only — drive labels can carry serials
                if "NVMe" in c.label:
                    drive_label["NVMe"] += 1
                elif "SSD" in c.label:
                    drive_label["SSD"] += 1
                elif "HDD" in c.label:
                    drive_label["HDD"] += 1
                else:
                    drive_label["other"] += 1
            elif c.group == "PSU" and c.capacity_value:
                psu_watts[int(c.capacity_value)] += 1
            elif c.group == "Port" and c.capacity_value:
                nic_speeds[f"{int(c.capacity_value)} {c.capacity_unit or 'Mbps'}"] += 1

    return {
        "by_group": dict(group_counts.most_common()),
        "top_part_numbers": dict(pn_counts.most_common(_TOP_PN_LIMIT)),
        "dimm_speed_mhz": dict(dimm_speed.most_common()),
        "dimm_type": dict(dimm_type.most_common()),
        "drive_media": dict(drive_label.most_common()),
        "psu_rated_watts": dict(sorted(psu_watts.items())),
        "nic_port_speeds": dict(nic_speeds.most_common()),
    }


def _hardware_shape(servers: list[Server]) -> dict[str, Any]:
    generation_mix: Counter[str] = Counter()
    form_factor_mix: Counter[str] = Counter()
    health_mix: Counter[str] = Counter()
    cores_buckets: Counter[str] = Counter()
    threads_buckets: Counter[str] = Counter()
    mem_buckets: Counter[str] = Counter()
    storage_buckets: Counter[str] = Counter()
    psu_buckets: Counter[str] = Counter()

    for s in servers:
        if s.generation:
            generation_mix[s.generation] += 1
        if s.form_factor:
            form_factor_mix[s.form_factor] += 1
        health_mix[(s.health or "unknown").lower()] += 1

        cores = sum((c.extra or {}).get("cores", 0) or 0 for c in s.components if c.group == "CPU")
        threads = sum((c.extra or {}).get("threads", 0) or 0 for c in s.components if c.group == "CPU")
        psu_watts = sum((c.capacity_value or 0) for c in s.components if c.group == "PSU")
        if cores:
            cores_buckets[_bucket_label(cores, _CORE_BUCKETS)] += 1
        if threads:
            threads_buckets[_bucket_label(threads, _CORE_BUCKETS)] += 1
        if s.total_memory_gb:
            mem_buckets[_bucket_label(s.total_memory_gb, _MEM_BUCKETS_GB) + " GB"] += 1
        if s.total_storage_gb:
            storage_buckets[_bucket_label(s.total_storage_gb, _STORAGE_BUCKETS_GB) + " GB"] += 1
        if psu_watts:
            psu_buckets[_bucket_label(psu_watts, _PSU_BUCKETS_W) + " W"] += 1

    return {
        "generation_mix": dict(generation_mix.most_common()),
        "form_factor_mix": dict(form_factor_mix.most_common()),
        "health_mix": dict(health_mix.most_common()),
        "cores_per_server": dict(cores_buckets.most_common()),
        "threads_per_server": dict(threads_buckets.most_common()),
        "memory_per_server": dict(mem_buckets.most_common()),
        "storage_per_server": dict(storage_buckets.most_common()),
        "psu_rated_watts_per_server": dict(psu_buckets.most_common()),
    }


def _platform_info() -> dict[str, str]:
    return {
        "os": platform.system().lower(),
        "os_release_major": platform.release().split(".")[0] if platform.release() else "",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "machine": platform.machine().lower(),
    }


def anonymized_export(session: Session, *, window_days: int = 30) -> dict[str, Any]:
    """`rollup` plus hardware-shape buckets, component distributions, per-mode
    and per-collector timings, host platform info. All counts, buckets and
    catalog identifiers — see module docstring for what's deliberately left out.
    """
    base = rollup(session, window_days=window_days)

    cutoff = datetime.utcnow() - timedelta(days=window_days)
    runs = session.scalars(select(Inventory).where(Inventory.created_at >= cutoff)).all()
    servers = [s for inv in runs for s in inv.servers]
    events = session.scalars(select(TelemetryEvent).where(TelemetryEvent.ts >= cutoff)).all()

    success = sum(1 for s in servers if (s.collection_status or "").lower() in {"ok", "success"})
    failure = sum(1 for s in servers if (s.collection_status or "").lower() in {"failed", "error"})

    base.update({
        "schema": "telemetry/anon-v2",
        "host_platform": _platform_info(),
        "hardware_shape": _hardware_shape(servers),
        "components": _component_stats(servers),
        "per_mode_duration_ms": _per_mode_duration(runs),
        "per_collector_timing_ms": _per_collector_timing(events),
        "host_outcomes": {
            "succeeded": success,
            "failed": failure,
            "success_rate": round(success / (success + failure), 3) if (success + failure) else 0.0,
        },
    })
    return base


def _percentiles(values: list[int], buckets: list[int]) -> dict[str, int]:
    out: dict[str, int] = {}
    if not values:
        return {f"p{b}": 0 for b in buckets}
    for b in buckets:
        idx = min(len(values) - 1, int(round(b / 100.0 * (len(values) - 1))))
        out[f"p{b}"] = values[idx]
    return out


def _classify_error(error: str | None) -> str:
    if not error:
        return "other"
    e = error.lower()
    if "401" in e:
        return "401_unauthorized"
    if "timeout" in e or "timed out" in e:
        return "timeout"
    if "cert" in e or "tls" in e or "ssl" in e:
        return "tls"
    if "unreachable" in e or "connection" in e:
        return "unreachable"
    if "schema" in e:
        return "ilo_schema"
    return "other"


def _daily_series(runs: list[Inventory], days: int) -> list[int]:
    bucket = Counter()
    for inv in runs:
        if not inv.created_at:
            continue
        day = inv.created_at.date()
        bucket[day] += 1
    today = datetime.utcnow().date()
    return [bucket[today - timedelta(days=days - 1 - i)] for i in range(days)]
