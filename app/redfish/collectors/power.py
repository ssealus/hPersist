from __future__ import annotations

from app.redfish.client import RedfishClient
from app.redfish.collectors.base import BaseCollector, CollectorResult, ComponentRow, safe_get


class PowerCollector(BaseCollector):
    name = "power"

    async def collect(self, client: RedfishClient, system: dict, chassis: dict, manager: dict) -> CollectorResult:
        components: list[ComponentRow] = []
        raw: dict[str, list] = {"PowerSupplies": [], "Fans": [], "Sensors": []}

        # PowerSubsystem (iLO 5/6) or Power (iLO 4)
        supplies: list[dict] = []
        ps_ref = safe_get(chassis, "PowerSubsystem", "@odata.id")
        if ps_ref:
            try:
                ps = await client.get(ps_ref)
                supplies = await client.walk(ps, "PowerSupplies")
            except Exception:
                supplies = []
        if not supplies:
            try:
                power = await client.get(safe_get(chassis, "Power", "@odata.id") or "/redfish/v1/Chassis/1/Power")
                supplies = power.get("PowerSupplies") or []
            except Exception:
                supplies = []

        for psu in supplies:
            raw["PowerSupplies"].append(psu)
            cap = safe_get(psu, "PowerCapacityWatts") or safe_get(psu, "PowerOutputWatts")
            components.append(
                ComponentRow(
                    group="PSU",
                    label=safe_get(psu, "Model") or safe_get(psu, "Name") or "Power Supply",
                    part_number=safe_get(psu, "Model") or safe_get(psu, "SparePartNumber"),
                    serial_number=safe_get(psu, "SerialNumber"),
                    manufacturer=safe_get(psu, "Manufacturer"),
                    firmware_version=safe_get(psu, "FirmwareVersion"),
                    location=str(safe_get(psu, "Id") or safe_get(psu, "MemberId") or "PS?"),
                    capacity_value=float(cap) if cap is not None else None,
                    capacity_unit="W",
                    health=safe_get(psu, "Status", "Health"),
                    extra={"type": safe_get(psu, "PowerSupplyType") or safe_get(psu, "LineInputVoltageType")},
                )
            )

        # thermal + sensors stay raw — not parts, not on the BOM
        thermal_ref = safe_get(chassis, "Thermal", "@odata.id") or safe_get(chassis, "ThermalSubsystem", "@odata.id")
        if thermal_ref:
            try:
                t = await client.get(thermal_ref)
                raw["Fans"] = t.get("Fans") or []
            except Exception:
                pass

        sensors_ref = safe_get(chassis, "Sensors", "@odata.id")
        if sensors_ref:
            try:
                sensors_root = await client.get(sensors_ref)
                # cap at 24 — some boxes expose 100+ sensors
                members = (sensors_root.get("Members") or [])[:24]
                for m in members:
                    try:
                        raw["Sensors"].append(await client.get(m["@odata.id"]))
                    except Exception:
                        continue
            except Exception:
                pass

        summary = {
            "psu_count": len(components),
            "rated_watts": sum(c.capacity_value or 0 for c in components),
            "redundancy_ok": len(components) >= 2,
        }
        return CollectorResult(components=components, raw=raw, summary=summary)
