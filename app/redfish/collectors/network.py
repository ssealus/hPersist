from __future__ import annotations

from app.redfish.client import RedfishClient
from app.redfish.collectors.base import BaseCollector, CollectorResult, ComponentRow, safe_get


class NetworkCollector(BaseCollector):
    name = "network"

    async def collect(self, client: RedfishClient, system: dict, chassis: dict, manager: dict) -> CollectorResult:
        adapters = await client.walk(chassis, "NetworkAdapters")
        eth_system = await client.walk(system, "EthernetInterfaces")
        components: list[ComponentRow] = []

        for a in adapters:
            controllers = safe_get(a, "Controllers") or []
            ports = sum((c.get("ControllerCapabilities", {}).get("NetworkPortCount", 0) for c in controllers), 0)
            fw = (controllers[0].get("FirmwarePackageVersion") if controllers else None) or safe_get(a, "FirmwareVersion")
            components.append(
                ComponentRow(
                    group="NIC",
                    label=(safe_get(a, "Model") or safe_get(a, "Name") or "Network adapter")[:200],
                    part_number=safe_get(a, "PartNumber") or safe_get(a, "SKU"),
                    serial_number=safe_get(a, "SerialNumber"),
                    manufacturer=safe_get(a, "Manufacturer"),
                    firmware_version=fw,
                    health=safe_get(a, "Status", "Health"),
                    location=safe_get(a, "Id"),
                    extra={"ports": ports},
                )
            )

        for e in eth_system:
            speed_mbps = safe_get(e, "SpeedMbps") or 0
            components.append(
                ComponentRow(
                    group="Port",
                    label=f"{safe_get(e, 'Name') or safe_get(e, 'Id')} · {speed_mbps} Mbps",
                    location=safe_get(e, "Id"),
                    capacity_value=speed_mbps,
                    capacity_unit="Mbps",
                    health=safe_get(e, "Status", "Health"),
                    extra={
                        "mac": safe_get(e, "MACAddress"),
                        "link_up": safe_get(e, "LinkStatus") in ("LinkUp", "Up"),
                        "ipv4": [a.get("Address") for a in (safe_get(e, "IPv4Addresses") or [])],
                    },
                )
            )

        summary = {
            "adapter_count": sum(1 for c in components if c.group == "NIC"),
            "port_count": sum(1 for c in components if c.group == "Port"),
        }
        return CollectorResult(
            components=components,
            raw={"NetworkAdapters": adapters, "EthernetInterfaces": eth_system},
            summary=summary,
        )
