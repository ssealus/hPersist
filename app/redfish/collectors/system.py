from __future__ import annotations

from app.redfish.client import RedfishClient
from app.redfish.collectors.base import BaseCollector, CollectorResult, ComponentRow, safe_get


class SystemCollector(BaseCollector):
    """Captures top-level system identity + the mainboard component row."""

    name = "system"

    async def collect(
        self, client: RedfishClient, system: dict, chassis: dict, manager: dict
    ) -> CollectorResult:
        sku = safe_get(system, "SKU") or safe_get(chassis, "SKU")
        part_number = safe_get(chassis, "PartNumber")
        model = safe_get(system, "Model") or safe_get(chassis, "Model")
        manufacturer = safe_get(system, "Manufacturer") or "HPE"
        sn = safe_get(system, "SerialNumber") or safe_get(chassis, "SerialNumber")
        bios = safe_get(system, "BiosVersion")
        uuid = safe_get(system, "UUID")
        host_name = safe_get(system, "HostName")
        chassis_type = safe_get(chassis, "ChassisType")
        asset_tag = safe_get(system, "AssetTag") or safe_get(chassis, "AssetTag")
        oem_hpe_id = safe_get(system, "Oem", "Hpe", "Bios", "Current", "Family")

        components = [
            ComponentRow(
                group="System",
                label=f"Mainboard · {model or 'Unknown'}",
                part_number=part_number,
                serial_number=sn,
                manufacturer=manufacturer,
                firmware_version=bios,
                health=safe_get(system, "Status", "Health"),
                location="mainboard",
                extra={"sku": sku, "uuid": uuid, "chassis_type": chassis_type, "asset_tag": asset_tag},
            )
        ]
        summary = {
            "model": model,
            "manufacturer": manufacturer,
            "sku": sku,
            "serial_number": sn,
            "hostname": host_name,
            "bios_version": bios,
            "form_factor": chassis_type,
            "uuid": uuid,
            "power_state": safe_get(system, "PowerState"),
            "health": safe_get(system, "Status", "HealthRollup") or safe_get(system, "Status", "Health"),
            "generation": _detect_generation(model, oem_hpe_id),
        }
        return CollectorResult(components=components, raw={"System": system, "Chassis": chassis}, summary=summary)


def _detect_generation(model: str | None, hpe_bios_family: str | None) -> str | None:
    if not model:
        return None
    m = model.upper()
    for token in ("GEN12", "GEN11", "GEN10 PLUS", "GEN10", "GEN9", "GEN8"):
        if token in m:
            return token.title()
    if hpe_bios_family:
        return hpe_bios_family
    return None
