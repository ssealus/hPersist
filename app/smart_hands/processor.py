"""Process a `results.hpr` envelope from the remote collector.

Six steps, each becomes a row in the UI progress panel:
envelope structure, metadata signature (seed match), per-host hash chain,
collector script SHA-256 (mismatch is a warning, not a block), schema
check, and persist. Script-modified envelopes are accepted because some
sites legitimately patch `collect.py` (proxies, custom auth).
"""
from __future__ import annotations

import dataclasses
import json
import tarfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.integrity import verify_chain
from app.core.logging import get_logger
from app.db import session_scope
from app.models import Component, Inventory, Server


@dataclass(slots=True)
class VerificationStep:
    label: str
    result: str          # ok | warn | err
    detail: str


@dataclass(slots=True)
class ProcessReport:
    inventory_id: str | None
    steps: list[VerificationStep] = field(default_factory=list)
    accepted: bool = False
    integrity_status: str = "unknown"
    summary: dict[str, Any] = field(default_factory=dict)

    def step(self, label: str, result: str, detail: str) -> None:
        self.steps.append(VerificationStep(label=label, result=result, detail=detail))

    def to_dict(self) -> dict:
        return {
            "inventory_id": self.inventory_id,
            "accepted": self.accepted,
            "integrity_status": self.integrity_status,
            "summary": self.summary,
            "steps": [dataclasses.asdict(s) for s in self.steps],
        }


def process_envelope(file_path: Path) -> ProcessReport:
    report = ProcessReport(inventory_id=None)

    try:
        with tarfile.open(file_path, "r:gz") as tf:
            try:
                envelope_member = tf.getmember("envelope.json")
            except KeyError:
                report.step("Envelope structure", "err", "no envelope.json in archive")
                return report
            envelope = json.loads(tf.extractfile(envelope_member).read())
        report.step("Envelope structure", "ok", f"tar.gz · envelope.json {envelope_member.size} B")
    except tarfile.ReadError:
        # bare JSON instead of the tarball — accept it with a warning
        try:
            envelope = json.loads(file_path.read_text(encoding="utf-8"))
            report.step("Envelope structure", "warn", "loose JSON envelope (no tar wrapper)")
        except Exception as exc:  # noqa: BLE001
            report.step("Envelope structure", "err", f"unreadable: {exc}")
            return report

    if envelope.get("schema") != "hpersist/v1":
        report.step("Results schema", "err", f"unexpected schema: {envelope.get('schema')}")
        return report

    meta = envelope.get("metadata") or {}
    inv_id = meta.get("inventory_id")
    seed_hex = meta.get("integrity_seed") or ""
    seed = bytes.fromhex(seed_hex) if seed_hex else b""

    # find the pending inventory: prefer the id from meta, fall back to seed match
    with session_scope() as s:
        target_inv: Inventory | None = None
        if inv_id:
            target_inv = s.get(Inventory, inv_id)
        if target_inv is None:
            stmt = select(Inventory).where(
                Inventory.integrity_seed == seed_hex,
                Inventory.submode == "script",
            )
            target_inv = s.scalars(stmt).first()

        if target_inv is None:
            report.step(
                "Metadata signature",
                "warn",
                "no matching pending inventory found — accepting as a new one",
            )
            target_inv = Inventory(
                name=meta.get("name") or f"Smart Hands import {datetime.utcnow():%Y-%m-%d}",
                organization=meta.get("organization"),
                description=meta.get("description"),
                mode="smart-hands",
                submode="process",
                integrity_seed=seed_hex or None,
                script_sha256=meta.get("expected_script_sha256"),
                collector_version=meta.get("generator_version"),
                created_by=meta.get("created_by"),
            )
            s.add(target_inv)
            s.flush()
        else:
            seed_ok = (target_inv.integrity_seed or "") == seed_hex
            report.step(
                "Metadata signature",
                "ok" if seed_ok else "err",
                f"seed match · pending inventory {target_inv.id}" if seed_ok else "seed mismatch",
            )
            if not seed_ok:
                return report

        report.inventory_id = target_inv.id
        logger = get_logger(target_inv.id)
        logger.info(f"processing Smart Hands envelope from {file_path.name}")

        chain = envelope.get("chain") or []
        results = envelope.get("results") or {}
        ok, issues = verify_chain(chain, results, seed) if seed else (False, ["no integrity seed"])
        if ok:
            report.step("Per-host hash chain", "ok", f"{len(chain)} hosts · no gaps")
        else:
            report.step("Per-host hash chain", "err", "; ".join(issues[:3]) or "verification failed")
            return report

        integ = envelope.get("integrity") or {}
        if integ.get("tamper_check") == "ok":
            report.step("Collector script integrity", "ok", f"sha256 {integ.get('script_sha256', '')[:12]}")
            target_inv.integrity_status = "ok"
            target_inv.integrity_notes = None
        else:
            note = (
                f"remote sha256 {integ.get('script_sha256', '')[:12]} differs from generator's "
                f"{integ.get('expected_script_sha256', '')[:12]}"
            )
            report.step("Collector script integrity", "warn", note + " — informational only")
            target_inv.integrity_status = "script-modified"
            target_inv.integrity_notes = note

        report.step("Results schema", "ok", f"hpersist/v1 · {envelope.get('host_count')} servers")

        target_inv.status = "complete" if envelope.get("failed", 0) == 0 else "complete-warn"
        target_inv.completed_at = datetime.utcnow()
        target_inv.duration_seconds = envelope.get("duration_seconds")
        target_inv.collector_version = meta.get("generator_version")

        # re-import: drop the servers from the previous run for this inventory
        for old in list(target_inv.servers):
            s.delete(old)
        s.flush()

        components_total = 0
        for host_key, payload in results.items():
            srv = _persist_server(s, target_inv, host_key, payload)
            components_total += len(srv.components)
            logger.ok(f"persisted {host_key} · {len(srv.components)} components")

        report.summary = {
            "servers": envelope.get("host_count"),
            "succeeded": envelope.get("succeeded"),
            "failed": envelope.get("failed"),
            "components": components_total,
        }
        report.step("Persist to local sqlite", "ok", f"{components_total} components · inv {target_inv.id}")
        report.accepted = True
        report.integrity_status = target_inv.integrity_status or "ok"

    return report


def _persist_server(session, inventory: Inventory, host_key: str, payload: dict) -> Server:
    summary_root = payload.get("summary") or {}
    sys_summ = summary_root.get("system") or {}
    mgr_summ = summary_root.get("manager") or {}
    mem_summ = summary_root.get("memory") or {}
    st_summ = summary_root.get("storage") or {}

    srv = Server(
        inventory_id=inventory.id,
        ilo_ip=payload.get("host") or host_key,
        hostname=payload.get("csv_hostname") or sys_summ.get("hostname"),
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
        collection_status="ok" if payload.get("success") else "failed",
        collection_error=payload.get("error"),
        duration_seconds=payload.get("duration_seconds"),
        raw_payload=payload.get("raw") or {},
    )
    session.add(srv)
    session.flush()

    for comp in payload.get("components") or []:
        session.add(
            Component(
                server_id=srv.id,
                group=comp.get("group") or "Other",
                label=comp.get("label") or "",
                part_number=comp.get("part_number"),
                serial_number=comp.get("serial_number"),
                location=comp.get("location"),
                manufacturer=comp.get("manufacturer"),
                quantity=comp.get("quantity") or 1,
                capacity_value=comp.get("capacity_value"),
                capacity_unit=comp.get("capacity_unit"),
                firmware_version=comp.get("firmware_version"),
                health=comp.get("health"),
                extra=comp.get("extra") or {},
            )
        )
    session.flush()
    return srv
