"""Collection job runner.

Bounded-concurrency Redfish sweep. Sync DB writes go through
``asyncio.to_thread`` — SQLite only takes one writer at a time, and we
don't want the event loop blocked while it queues on busy_timeout.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.logging import get_logger
from app.db import session_scope
from app.jobs.bus import bus
from app.models import CollectionJob, Component, Inventory, Server, TelemetryEvent
from app.redfish import RedfishCreds, collect_host


@dataclass(slots=True)
class HostSpec:
    ip: str
    hostname: str | None
    login: str
    password: str


async def run_collection_job(
    inventory_id: str,
    hosts: list[HostSpec],
    *,
    concurrency: int | None = None,
    timeout: float | None = None,
) -> None:
    concurrency = concurrency or settings.collector.concurrency
    timeout = timeout or settings.collector.timeout_seconds
    logger = get_logger(inventory_id)
    channel = f"job:{inventory_id}"

    sem = asyncio.Semaphore(concurrency)
    started_at = datetime.utcnow()
    started_perf = time.perf_counter()

    state: dict[str, dict] = {h.ip: {"ip": h.ip, "hostname": h.hostname, "progress": 0, "stage": "queued"} for h in hosts}

    def _init_job() -> bool:
        with session_scope() as s:
            inv = s.get(Inventory, inventory_id)
            if inv is None:
                return False
            inv.status = "in-progress"
            job = inv.job or CollectionJob(inventory_id=inventory_id)
            job.state = "running"
            job.total_hosts = len(hosts)
            job.completed = 0
            job.failed = 0
            job.started_at = started_at
            job.log_path = str(settings.data_dir / "logs" / f"{inventory_id}.log")
            s.add(job)
            return True

    if not await asyncio.to_thread(_init_job):
        logger.err(f"inventory {inventory_id} disappeared before run")
        return

    await bus.publish(channel, {"type": "job.start", "total": len(hosts), "started_at": started_at.isoformat(timespec="seconds")})
    logger.info(f"starting collection · {len(hosts)} host(s) · concurrency={concurrency}")

    async def work(spec: HostSpec) -> None:
        async with sem:
            state[spec.ip]["stage"] = "auth"
            await bus.publish(channel, {"type": "host.start", "host": spec.ip})
            creds = RedfishCreds(username=spec.login, password=spec.password, tls_verify=settings.collector.tls_verify)
            t0 = time.perf_counter()

            async def tick(stage: str, percent: int) -> None:
                state[spec.ip].update(stage=stage, progress=percent)
                await bus.publish(channel, {"type": "host.progress", "host": spec.ip, "stage": stage, "progress": percent})

            await tick("probe", 5)
            record = await collect_host(spec.ip, creds, timeout=timeout, logger=logger)
            duration_ms = int((time.perf_counter() - t0) * 1000)

            try:
                if record.success:
                    await tick("persist", 95)
                    await asyncio.to_thread(_persist, inventory_id, spec, record)
                    state[spec.ip].update(stage="done", progress=100, duration=record.duration_seconds)
                    await bus.publish(channel, {"type": "host.done", "host": spec.ip, "duration": record.duration_seconds, "components": len(record.components)})
                else:
                    state[spec.ip].update(stage="error", progress=100, error=record.error)
                    await bus.publish(channel, {"type": "host.failed", "host": spec.ip, "error": record.error})
                    await asyncio.to_thread(_record_failure, inventory_id, spec, record)

                await asyncio.to_thread(_record_host_telemetry, inventory_id, duration_ms, record.success)
            except IntegrityError:
                # inventory got deleted while we were collecting; don't crash the gather
                logger.warn(f"{spec.ip}: inventory disappeared mid-run, skipping persist")
                state[spec.ip].update(stage="cancelled", progress=100)

    await asyncio.gather(*(work(h) for h in hosts), return_exceptions=False)

    finished_at = datetime.utcnow()
    duration_seconds = round(time.perf_counter() - started_perf, 3)

    finalize_result = await asyncio.to_thread(_finalize_job, inventory_id, finished_at, duration_seconds, len(hosts))
    if finalize_result is None:
        # inventory got deleted before finalize; nothing left to publish
        logger.warn(f"inventory {inventory_id} disappeared before finalize, skipping")
        return

    completed, failed = finalize_result
    await bus.publish(channel, {"type": "job.done", "duration": duration_seconds, "completed": completed, "failed": failed})
    logger.ok(f"collection finished · {duration_seconds:.1f}s")


def _job_select(inventory_id: str):
    from sqlalchemy import select

    return select(CollectionJob).where(CollectionJob.inventory_id == inventory_id)


def _record_failure(inventory_id: str, spec: HostSpec, record: Any) -> None:
    with session_scope() as s:
        s.add(Server(
            inventory_id=inventory_id,
            ilo_ip=spec.ip,
            hostname=spec.hostname,
            collection_status="failed",
            collection_error=record.error,
            duration_seconds=record.duration_seconds,
        ))


def _record_host_telemetry(inventory_id: str, duration_ms: int, success: bool) -> None:
    with session_scope() as s:
        s.add(TelemetryEvent(
            kind="host.timing",
            mode="local",
            duration_ms=duration_ms,
            payload={"success": success},
        ))
        job = s.execute(_job_select(inventory_id)).scalar_one()
        if success:
            job.completed += 1
        else:
            job.failed += 1


def _finalize_job(inventory_id: str, finished_at: datetime, duration_seconds: float, total: int) -> tuple[int, int] | None:
    with session_scope() as s:
        inv = s.get(Inventory, inventory_id)
        if inv is None:
            return None
        job = s.execute(_job_select(inventory_id)).scalar_one_or_none()
        if job is None:
            return None
        job.state = "done"
        job.finished_at = finished_at
        inv.completed_at = finished_at
        inv.duration_seconds = duration_seconds
        if job.failed == 0:
            inv.status = "complete"
        elif job.completed == 0:
            inv.status = "failed"
        else:
            inv.status = "complete-warn"

        s.add(TelemetryEvent(
            kind="collection.finish",
            mode=inv.mode,
            duration_ms=int(duration_seconds * 1000),
            payload={"total": total, "completed": job.completed, "failed": job.failed},
        ))
        return job.completed, job.failed


def _persist(inventory_id: str, spec: HostSpec, record: Any) -> None:
    sys_summ = record.summary.get("system", {})
    mgr_summ = record.summary.get("manager", {})
    mem_summ = record.summary.get("memory", {})
    st_summ = record.summary.get("storage", {})

    with session_scope() as s:
        srv = Server(
            inventory_id=inventory_id,
            ilo_ip=spec.ip,
            hostname=spec.hostname or sys_summ.get("hostname"),
            serial_number=sys_summ.get("serial_number"),
            sku=sys_summ.get("sku"),
            model=sys_summ.get("model"),
            manufacturer=sys_summ.get("manufacturer") or "HPE",
            form_factor=sys_summ.get("form_factor"),
            generation=sys_summ.get("generation"),
            ilo_generation=mgr_summ.get("generation"),
            ilo_firmware=mgr_summ.get("firmware_version"),
            bios_version=sys_summ.get("bios_version"),
            power_state=sys_summ.get("power_state"),
            health=sys_summ.get("health"),
            total_memory_gb=mem_summ.get("total_gb"),
            total_storage_gb=st_summ.get("total_gb"),
            duration_seconds=record.duration_seconds,
            raw_payload=record.raw,
        )
        s.add(srv)
        s.flush()
        for c in record.components:
            s.add(Component(
                server_id=srv.id,
                group=c.group,
                label=c.label,
                part_number=c.part_number,
                serial_number=c.serial_number,
                location=c.location,
                manufacturer=c.manufacturer,
                quantity=c.quantity,
                capacity_value=c.capacity_value,
                capacity_unit=c.capacity_unit,
                firmware_version=c.firmware_version,
                health=c.health,
                extra=c.extra,
            ))


async def schedule(inventory_id: str, hosts: list[HostSpec], *, concurrency: int | None = None, timeout: float | None = None) -> asyncio.Task:
    """Schedule a collection job as a background task on the running event loop."""
    return asyncio.get_running_loop().create_task(
        run_collection_job(inventory_id, hosts, concurrency=concurrency, timeout=timeout)
    )
