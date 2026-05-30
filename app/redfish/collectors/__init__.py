"""Default collector pipeline.

Order matters only for log readability — each collector is independent.
"""
from __future__ import annotations

from app.redfish.collectors.base import BaseCollector, CollectorResult, ComponentRow
from app.redfish.collectors.manager import ManagerCollector
from app.redfish.collectors.memory import MemoryCollector
from app.redfish.collectors.network import NetworkCollector
from app.redfish.collectors.pci import PCICollector
from app.redfish.collectors.power import PowerCollector
from app.redfish.collectors.processor import ProcessorCollector
from app.redfish.collectors.storage import StorageCollector
from app.redfish.collectors.system import SystemCollector


COLLECTORS: list[BaseCollector] = [
    SystemCollector(),
    ManagerCollector(),
    ProcessorCollector(),
    MemoryCollector(),
    StorageCollector(),
    NetworkCollector(),
    PCICollector(),
    PowerCollector(),
]


__all__ = ["COLLECTORS", "BaseCollector", "CollectorResult", "ComponentRow"]
