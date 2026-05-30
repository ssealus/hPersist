from __future__ import annotations

from app.redfish.client import RedfishClient
from app.redfish.collectors.base import BaseCollector, CollectorResult, ComponentRow, safe_get


class StorageCollector(BaseCollector):
    name = "storage"

    async def collect(self, client: RedfishClient, system: dict, chassis: dict, manager: dict) -> CollectorResult:
        controllers_raw: list[dict] = []
        drives_raw: list[dict] = []
        components: list[ComponentRow] = []
        total_bytes = 0

        for st in await client.walk(system, "Storage"):
            ctrl_label = safe_get(st, "Name") or safe_get(st, "Id") or "Storage Controller"

            for ctrl in await client.walk(st, "Controllers"):
                controllers_raw.append(ctrl)
                components.append(
                    ComponentRow(
                        group="Controller",
                        label=safe_get(ctrl, "Model") or ctrl_label,
                        part_number=safe_get(ctrl, "PartNumber"),
                        serial_number=safe_get(ctrl, "SerialNumber"),
                        manufacturer=safe_get(ctrl, "Manufacturer"),
                        firmware_version=safe_get(ctrl, "FirmwareVersion"),
                        health=safe_get(ctrl, "Status", "Health"),
                        location=safe_get(st, "Id"),
                    )
                )

            for drive_ref in (st.get("Drives") or []):
                url = drive_ref.get("@odata.id")
                if not url:
                    continue
                try:
                    d = await client.get(url)
                except Exception:
                    continue
                drives_raw.append(d)

                bay = safe_get(d, "PhysicalLocation", "PartLocation", "ServiceLabel") or safe_get(d, "Id")
                cap = safe_get(d, "CapacityBytes") or 0
                if cap:
                    total_bytes += cap
                cap_gb = round(cap / 1e9, 2) if cap else None
                media = safe_get(d, "MediaType") or "SSD"
                protocol = safe_get(d, "Protocol") or ""

                label = f"{cap_gb:.0f}GB {protocol} {media}".strip() if cap_gb else (safe_get(d, "Name") or "Drive")
                components.append(
                    ComponentRow(
                        group="Drive",
                        label=label,
                        part_number=safe_get(d, "PartNumber"),
                        serial_number=safe_get(d, "SerialNumber"),
                        manufacturer=safe_get(d, "Manufacturer"),
                        firmware_version=safe_get(d, "Revision"),
                        location=str(bay),
                        capacity_value=cap_gb,
                        capacity_unit="GB",
                        health=safe_get(d, "Status", "Health"),
                        extra={
                            "media": media,
                            "protocol": protocol,
                            "failure_predicted": safe_get(d, "FailurePredicted"),
                            "encrypted": safe_get(d, "EncryptionStatus"),
                            "rpm": safe_get(d, "RotationSpeedRPM"),
                        },
                    )
                )

        summary = {
            "controllers": len(controllers_raw),
            "drives": sum(1 for c in components if c.group == "Drive"),
            "total_gb": round(total_bytes / 1e9, 2),
        }
        return CollectorResult(
            components=components,
            raw={"Storage": controllers_raw, "Drives": drives_raw},
            summary=summary,
        )
