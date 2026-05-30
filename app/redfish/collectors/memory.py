from __future__ import annotations

from app.redfish.client import RedfishClient
from app.redfish.collectors.base import BaseCollector, CollectorResult, ComponentRow, safe_get


class MemoryCollector(BaseCollector):
    name = "memory"

    async def collect(self, client: RedfishClient, system: dict, chassis: dict, manager: dict) -> CollectorResult:
        dimms = await client.walk(system, "Memory")
        components: list[ComponentRow] = []
        total_gb = 0.0

        for d in dimms:
            cap_mib = safe_get(d, "CapacityMiB")
            if not cap_mib:
                continue
            cap_gb = round(cap_mib / 1024.0, 2)
            total_gb += cap_gb
            location = safe_get(d, "DeviceLocator") or safe_get(d, "Name")
            kind = safe_get(d, "MemoryDeviceType") or "DDR?"
            base = safe_get(d, "BaseModuleType") or ""
            speed = safe_get(d, "OperatingSpeedMhz") or 0

            label = f"{cap_gb:.0f}GB {kind} {base} {speed}MT/s".strip()
            components.append(
                ComponentRow(
                    group="DIMM",
                    label=label,
                    part_number=safe_get(d, "PartNumber"),
                    serial_number=safe_get(d, "SerialNumber"),
                    location=location,
                    manufacturer=safe_get(d, "Manufacturer"),
                    capacity_value=cap_gb,
                    capacity_unit="GB",
                    health=safe_get(d, "Status", "Health"),
                    extra={
                        "type": kind,
                        "speed_mts": speed,
                        "rank_count": safe_get(d, "RankCount"),
                        "ecc": safe_get(d, "ErrorCorrection"),
                        "channel": safe_get(d, "MemoryLocation", "Channel"),
                        "socket": safe_get(d, "MemoryLocation", "Socket"),
                    },
                )
            )

        summary = {
            "dimm_count": len(components),
            "total_gb": round(total_gb, 2),
            "speed_distribution": _bucket(components, "speed_mts"),
            "type_distribution": _bucket(components, "type"),
        }
        return CollectorResult(components=components, raw={"Memory": dimms}, summary=summary)


def _bucket(components: list[ComponentRow], key: str) -> dict:
    out: dict[str, int] = {}
    for c in components:
        k = str(c.extra.get(key, "")).strip() or "—"
        out[k] = out.get(k, 0) + 1
    return out
