from __future__ import annotations

import re

from app.redfish.client import RedfishClient
from app.redfish.collectors.base import BaseCollector, CollectorResult, safe_get


class ManagerCollector(BaseCollector):
    """Captures iLO identity, firmware and MAC."""

    name = "manager"

    async def collect(self, client: RedfishClient, system: dict, chassis: dict, manager: dict) -> CollectorResult:
        fw_full = safe_get(manager, "FirmwareVersion") or ""
        model = safe_get(manager, "Model") or ""

        # iLO 5/6: "iLO 5 v3.11" — both pieces in FirmwareVersion
        m = re.search(r"iLO\s*(\d+)[^\d]*([0-9]+(?:\.[0-9]+)+)", fw_full, re.IGNORECASE)
        if m:
            generation = f"iLO {m.group(1)}"
            fw = m.group(2)
        else:
            # Gen12 splits them: Model="iLO 7", FirmwareVersion="1.13.01 May 13 2025".
            # Grab the first dotted version, not the last token — that's the build year.
            gm = re.search(r"iLO\s*(\d+)", model, re.IGNORECASE)
            generation = f"iLO {gm.group(1)}" if gm else (model or None)
            fm = re.search(r"\b(\d+(?:\.\d+)+)\b", fw_full)
            fw = fm.group(1) if fm else None

        eth: list[dict] = []
        for url_key in ("EthernetInterfaces", "DedicatedNetworkPorts"):
            eth.extend(await client.walk(manager, url_key))

        macs = [safe_get(e, "MACAddress") for e in eth if safe_get(e, "MACAddress")]

        summary = {
            "generation": generation,
            "firmware_version": fw,
            "firmware_raw": fw_full,
            "model": safe_get(manager, "Model"),
            "uuid": safe_get(manager, "UUID"),
            "macs": macs,
        }
        return CollectorResult(components=[], raw={"Manager": manager, "ManagerEthernet": eth}, summary=summary)
