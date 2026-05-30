from __future__ import annotations

from app.redfish.client import RedfishClient
from app.redfish.collectors.base import BaseCollector, CollectorResult, ComponentRow, safe_get


class ProcessorCollector(BaseCollector):
    name = "processor"

    async def collect(self, client: RedfishClient, system: dict, chassis: dict, manager: dict) -> CollectorResult:
        procs = await client.walk(system, "Processors")
        components: list[ComponentRow] = []
        models: dict[str, dict] = {}

        for p in procs:
            if safe_get(p, "ProcessorType") not in (None, "CPU"):
                continue
            model = safe_get(p, "Model") or "Unknown CPU"
            socket = safe_get(p, "Socket") or safe_get(p, "Id")
            cores = safe_get(p, "TotalCores") or 0
            threads = safe_get(p, "TotalThreads") or 0
            ghz = (safe_get(p, "MaxSpeedMHz") or 0) / 1000.0 or None
            tdp = safe_get(p, "TDPWatts") or safe_get(p, "Oem", "Hpe", "RatedSpeedMHz")
            health = safe_get(p, "Status", "Health")
            sn = safe_get(p, "SerialNumber")

            components.append(
                ComponentRow(
                    group="CPU",
                    label=model.strip(),
                    serial_number=sn,
                    location=str(socket),
                    manufacturer=safe_get(p, "Manufacturer"),
                    part_number=safe_get(p, "PartNumber") or None,
                    capacity_value=ghz,
                    capacity_unit="GHz",
                    health=health,
                    extra={"cores": cores, "threads": threads, "tdp_watts": tdp, "architecture": safe_get(p, "ProcessorArchitecture")},
                )
            )
            models.setdefault(model.strip(), {"cores": cores, "threads": threads, "ghz": ghz, "count": 0})
            models[model.strip()]["count"] += 1

        summary = {
            "count": len(components),
            "models": models,
            "total_cores": sum(c.extra.get("cores", 0) for c in components),
            "total_threads": sum(c.extra.get("threads", 0) for c in components),
        }
        return CollectorResult(components=components, raw={"Processors": procs}, summary=summary)
