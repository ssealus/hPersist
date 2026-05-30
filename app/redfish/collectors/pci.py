from __future__ import annotations

from app.redfish.client import RedfishClient
from app.redfish.collectors.base import BaseCollector, CollectorResult, ComponentRow, safe_get


class PCICollector(BaseCollector):
    name = "pci"

    async def collect(self, client: RedfishClient, system: dict, chassis: dict, manager: dict) -> CollectorResult:
        devices: list[dict] = []
        for source in ("PCIeDevices", "PCIDevices"):
            devices.extend(await client.walk(chassis, source))
            devices.extend(await client.walk(system, source))

        seen: set[str] = set()
        components: list[ComponentRow] = []
        for d in devices:
            uid = safe_get(d, "@odata.id") or safe_get(d, "Id")
            if uid in seen:
                continue
            seen.add(uid)
            label = safe_get(d, "Model") or safe_get(d, "Name") or "PCIe device"
            components.append(
                ComponentRow(
                    group="PCIe",
                    label=label[:200],
                    part_number=safe_get(d, "PartNumber") or safe_get(d, "SKU"),
                    serial_number=safe_get(d, "SerialNumber"),
                    manufacturer=safe_get(d, "Manufacturer"),
                    firmware_version=safe_get(d, "FirmwareVersion"),
                    location=safe_get(d, "Id"),
                    health=safe_get(d, "Status", "Health"),
                    extra={"device_type": safe_get(d, "DeviceType")},
                )
            )

        return CollectorResult(components=components, raw={"PCIeDevices": devices}, summary={"count": len(components)})
