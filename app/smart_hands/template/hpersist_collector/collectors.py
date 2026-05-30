"""Standalone component collectors.

Same logic as the in-app ones, just collapsed into one module since the
archive ships to a stranger's host where simpler layout = fewer surprises.
"""
from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .client import RedfishClient, RedfishError


def _g(d: dict, *path, default=None):
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


@dataclass(slots=True)
class ComponentRow:
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
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


async def collect_system(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]:
    model = _g(system, "Model") or _g(chassis, "Model")
    sn = _g(system, "SerialNumber") or _g(chassis, "SerialNumber")
    sku = _g(system, "SKU") or _g(chassis, "SKU")
    pn = _g(chassis, "PartNumber")
    bios = _g(system, "BiosVersion")
    uuid = _g(system, "UUID")
    rows = [
        ComponentRow(
            group="System",
            label=f"Mainboard · {model or 'Unknown'}",
            part_number=pn,
            serial_number=sn,
            manufacturer=_g(system, "Manufacturer") or "HPE",
            firmware_version=bios,
            health=_g(system, "Status", "Health"),
            location="mainboard",
            extra={"sku": sku, "uuid": uuid, "asset_tag": _g(system, "AssetTag")},
        )
    ]
    summary = {
        "model": model, "sku": sku, "serial_number": sn,
        "hostname": _g(system, "HostName"),
        "bios_version": bios,
        "form_factor": _g(chassis, "ChassisType"),
        "uuid": uuid,
        "power_state": _g(system, "PowerState"),
        "health": _g(system, "Status", "HealthRollup") or _g(system, "Status", "Health"),
        "generation": _gen(model),
    }
    return rows, {"System": system, "Chassis": chassis}, summary


def _gen(model):
    if not model:
        return None
    for t in ("Gen12", "Gen11", "Gen10 Plus", "Gen10", "Gen9", "Gen8"):
        if t.lower() in model.lower():
            return t
    return None


async def collect_manager(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]:
    fw = _g(manager, "FirmwareVersion") or ""
    model = _g(manager, "Model") or ""
    m = re.search(r"iLO\s*(\d+)[^\d]*([0-9]+(?:\.[0-9]+)+)", fw, re.IGNORECASE)
    if m:
        gen = f"iLO {m.group(1)}"
        fwver = m.group(2)
    else:
        gm = re.search(r"iLO\s*(\d+)", model, re.IGNORECASE)
        gen = f"iLO {gm.group(1)}" if gm else (model or None)
        fm = re.search(r"\b(\d+(?:\.\d+)+)\b", fw)
        fwver = fm.group(1) if fm else None
    eth = await client.walk(manager, "EthernetInterfaces")
    return [], {"Manager": manager, "ManagerEthernet": eth}, {
        "generation": gen, "firmware_version": fwver, "firmware_raw": fw,
        "macs": [_g(e, "MACAddress") for e in eth if _g(e, "MACAddress")],
    }


async def collect_processors(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]:
    procs = await client.walk(system, "Processors")
    rows: list[ComponentRow] = []
    for p in procs:
        if _g(p, "ProcessorType") not in (None, "CPU"):
            continue
        model = _g(p, "Model") or "Unknown CPU"
        rows.append(ComponentRow(
            group="CPU",
            label=model.strip(),
            serial_number=_g(p, "SerialNumber"),
            location=str(_g(p, "Socket") or _g(p, "Id")),
            manufacturer=_g(p, "Manufacturer"),
            part_number=_g(p, "PartNumber") or None,
            capacity_value=(_g(p, "MaxSpeedMHz") or 0) / 1000.0 or None,
            capacity_unit="GHz",
            health=_g(p, "Status", "Health"),
            extra={"cores": _g(p, "TotalCores") or 0, "threads": _g(p, "TotalThreads") or 0,
                   "tdp_watts": _g(p, "TDPWatts"), "architecture": _g(p, "ProcessorArchitecture")},
        ))
    return rows, {"Processors": procs}, {
        "count": len(rows),
        "total_cores": sum(c.extra.get("cores", 0) for c in rows),
        "total_threads": sum(c.extra.get("threads", 0) for c in rows),
    }


async def collect_memory(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]:
    dimms = await client.walk(system, "Memory")
    rows: list[ComponentRow] = []
    total = 0.0
    for d in dimms:
        cap_mib = _g(d, "CapacityMiB") or 0
        if not cap_mib:
            continue
        cap_gb = round(cap_mib / 1024.0, 2)
        total += cap_gb
        rows.append(ComponentRow(
            group="DIMM",
            label=f"{cap_gb:.0f}GB {_g(d, 'MemoryDeviceType') or 'DDR?'} {_g(d, 'BaseModuleType') or ''} {_g(d, 'OperatingSpeedMhz') or 0}MT/s".strip(),
            part_number=_g(d, "PartNumber"),
            serial_number=_g(d, "SerialNumber"),
            location=_g(d, "DeviceLocator") or _g(d, "Name"),
            manufacturer=_g(d, "Manufacturer"),
            capacity_value=cap_gb,
            capacity_unit="GB",
            health=_g(d, "Status", "Health"),
            extra={"type": _g(d, "MemoryDeviceType"), "speed_mts": _g(d, "OperatingSpeedMhz"),
                   "rank_count": _g(d, "RankCount"), "ecc": _g(d, "ErrorCorrection")},
        ))
    return rows, {"Memory": dimms}, {"dimm_count": len(rows), "total_gb": round(total, 2)}


async def collect_storage(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]:
    rows: list[ComponentRow] = []
    controllers_raw: list[dict] = []
    drives_raw: list[dict] = []
    total_bytes = 0

    for st in await client.walk(system, "Storage"):
        for ctrl in await client.walk(st, "Controllers"):
            controllers_raw.append(ctrl)
            rows.append(ComponentRow(
                group="Controller",
                label=_g(ctrl, "Model") or _g(st, "Name") or "Storage Controller",
                part_number=_g(ctrl, "PartNumber"),
                serial_number=_g(ctrl, "SerialNumber"),
                manufacturer=_g(ctrl, "Manufacturer"),
                firmware_version=_g(ctrl, "FirmwareVersion"),
                health=_g(ctrl, "Status", "Health"),
                location=_g(st, "Id"),
            ))
        for ref in (st.get("Drives") or []):
            url = ref.get("@odata.id")
            if not url:
                continue
            try:
                d = await client.get(url)
            except RedfishError:
                continue
            drives_raw.append(d)
            cap = _g(d, "CapacityBytes") or 0
            if cap:
                total_bytes += cap
            cap_gb = round(cap / 1e9, 2) if cap else None
            media = _g(d, "MediaType") or "SSD"
            protocol = _g(d, "Protocol") or ""
            bay = _g(d, "PhysicalLocation", "PartLocation", "ServiceLabel") or _g(d, "Id")
            rows.append(ComponentRow(
                group="Drive",
                label=f"{cap_gb:.0f}GB {protocol} {media}".strip() if cap_gb else (_g(d, "Name") or "Drive"),
                part_number=_g(d, "PartNumber"),
                serial_number=_g(d, "SerialNumber"),
                manufacturer=_g(d, "Manufacturer"),
                firmware_version=_g(d, "Revision"),
                location=str(bay),
                capacity_value=cap_gb,
                capacity_unit="GB",
                health=_g(d, "Status", "Health"),
                extra={"media": media, "protocol": protocol,
                       "failure_predicted": _g(d, "FailurePredicted"),
                       "encrypted": _g(d, "EncryptionStatus")},
            ))
    return rows, {"Storage": controllers_raw, "Drives": drives_raw}, {
        "controllers": len(controllers_raw),
        "drives": sum(1 for r in rows if r.group == "Drive"),
        "total_gb": round(total_bytes / 1e9, 2),
    }


async def collect_network(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]:
    adapters = await client.walk(chassis, "NetworkAdapters")
    eth = await client.walk(system, "EthernetInterfaces")
    rows: list[ComponentRow] = []
    for a in adapters:
        ctrls = _g(a, "Controllers") or []
        ports = sum((c.get("ControllerCapabilities", {}).get("NetworkPortCount", 0) for c in ctrls), 0)
        fw = (ctrls[0].get("FirmwarePackageVersion") if ctrls else None) or _g(a, "FirmwareVersion")
        rows.append(ComponentRow(
            group="NIC",
            label=(_g(a, "Model") or _g(a, "Name") or "Network adapter")[:200],
            part_number=_g(a, "PartNumber") or _g(a, "SKU"),
            serial_number=_g(a, "SerialNumber"),
            manufacturer=_g(a, "Manufacturer"),
            firmware_version=fw,
            health=_g(a, "Status", "Health"),
            location=_g(a, "Id"),
            extra={"ports": ports},
        ))
    for e in eth:
        rows.append(ComponentRow(
            group="Port",
            label=f"{_g(e, 'Name') or _g(e, 'Id')} · {_g(e, 'SpeedMbps') or 0} Mbps",
            location=_g(e, "Id"),
            capacity_value=_g(e, "SpeedMbps") or 0,
            capacity_unit="Mbps",
            health=_g(e, "Status", "Health"),
            extra={"mac": _g(e, "MACAddress"),
                   "link_up": _g(e, "LinkStatus") in ("LinkUp", "Up")},
        ))
    return rows, {"NetworkAdapters": adapters, "EthernetInterfaces": eth}, {
        "adapter_count": sum(1 for r in rows if r.group == "NIC"),
        "port_count": sum(1 for r in rows if r.group == "Port"),
    }


async def collect_pci(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]:
    devs: list[dict] = []
    for key in ("PCIeDevices", "PCIDevices"):
        devs.extend(await client.walk(chassis, key))
        devs.extend(await client.walk(system, key))
    seen, rows = set(), []
    for d in devs:
        uid = _g(d, "@odata.id") or _g(d, "Id")
        if uid in seen:
            continue
        seen.add(uid)
        rows.append(ComponentRow(
            group="PCIe",
            label=(_g(d, "Model") or _g(d, "Name") or "PCIe device")[:200],
            part_number=_g(d, "PartNumber") or _g(d, "SKU"),
            serial_number=_g(d, "SerialNumber"),
            manufacturer=_g(d, "Manufacturer"),
            firmware_version=_g(d, "FirmwareVersion"),
            location=_g(d, "Id"),
            health=_g(d, "Status", "Health"),
        ))
    return rows, {"PCIeDevices": devs}, {"count": len(rows)}


async def collect_power(client, system, chassis, manager) -> tuple[list[ComponentRow], dict, dict]:
    rows: list[ComponentRow] = []
    raw: dict = {"PowerSupplies": [], "Fans": [], "Sensors": []}
    supplies: list[dict] = []

    ps_ref = _g(chassis, "PowerSubsystem", "@odata.id")
    if ps_ref:
        try:
            ps = await client.get(ps_ref)
            supplies = await client.walk(ps, "PowerSupplies")
        except RedfishError:
            pass
    if not supplies:
        try:
            power = await client.get(_g(chassis, "Power", "@odata.id") or "/redfish/v1/Chassis/1/Power")
            supplies = power.get("PowerSupplies") or []
        except RedfishError:
            pass

    for psu in supplies:
        raw["PowerSupplies"].append(psu)
        cap = _g(psu, "PowerCapacityWatts") or _g(psu, "PowerOutputWatts")
        rows.append(ComponentRow(
            group="PSU",
            label=_g(psu, "Model") or _g(psu, "Name") or "Power Supply",
            part_number=_g(psu, "Model") or _g(psu, "SparePartNumber"),
            serial_number=_g(psu, "SerialNumber"),
            manufacturer=_g(psu, "Manufacturer"),
            firmware_version=_g(psu, "FirmwareVersion"),
            location=str(_g(psu, "Id") or _g(psu, "MemberId") or "PS?"),
            capacity_value=float(cap) if cap is not None else None,
            capacity_unit="W",
            health=_g(psu, "Status", "Health"),
        ))

    thermal_ref = _g(chassis, "Thermal", "@odata.id") or _g(chassis, "ThermalSubsystem", "@odata.id")
    if thermal_ref:
        try:
            t = await client.get(thermal_ref)
            raw["Fans"] = t.get("Fans") or []
        except RedfishError:
            pass

    sensors_ref = _g(chassis, "Sensors", "@odata.id")
    if sensors_ref:
        try:
            sensors_root = await client.get(sensors_ref)
            for m in (sensors_root.get("Members") or [])[:24]:
                try:
                    raw["Sensors"].append(await client.get(m["@odata.id"]))
                except RedfishError:
                    continue
        except RedfishError:
            pass

    return rows, raw, {
        "psu_count": len(rows),
        "rated_watts": sum(r.capacity_value or 0 for r in rows),
        "redundancy_ok": len(rows) >= 2,
    }


COLLECTORS = [
    ("system", collect_system),
    ("manager", collect_manager),
    ("processor", collect_processors),
    ("memory", collect_memory),
    ("storage", collect_storage),
    ("network", collect_network),
    ("pci", collect_pci),
    ("power", collect_power),
]
