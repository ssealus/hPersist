"""Asynchronous CIDR sweep.

We don't use raw ICMP (requires root); the heuristic is:
``TCP/443 open`` -> reachable, then ``GET /redfish/v1/`` decides if it's a
candidate. Results stream out as they happen so the UI can render incrementally.
"""
from __future__ import annotations

import asyncio
import ipaddress
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.redfish.client import RedfishClient, RedfishCreds


@dataclass(slots=True)
class ScanHit:
    ip: str
    reachable: bool
    tcp_443: bool = False
    redfish: bool = False
    rtt_ms: float | None = None
    server_header: str | None = None
    error: str | None = None
    is_hpe: bool | None = None


@dataclass(slots=True)
class ScanProgress:
    total: int
    done: int = 0
    hits: list[ScanHit] = field(default_factory=list)


async def expand_cidr(cidr: str, *, max_hosts: int = 65536) -> list[str]:
    net = ipaddress.ip_network(cidr, strict=False)
    if net.num_addresses > max_hosts:
        raise ValueError(f"network too large ({net.num_addresses} > {max_hosts}); narrow the range")
    return [str(h) for h in (net.hosts() if net.num_addresses > 2 else net)]


async def _probe_tcp(ip: str, port: int, timeout: float) -> tuple[bool, float | None]:
    loop = asyncio.get_event_loop()
    started = loop.time()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, (loop.time() - started) * 1000
    except (TimeoutError, OSError):
        return False, None


async def _classify(ip: str, *, probe_redfish: bool, timeout: float) -> ScanHit:
    tcp_ok, rtt = await _probe_tcp(ip, 443, timeout)
    if not tcp_ok:
        return ScanHit(ip=ip, reachable=False, tcp_443=False, rtt_ms=rtt)
    if not probe_redfish:
        return ScanHit(ip=ip, reachable=True, tcp_443=True, rtt_ms=rtt)
    try:
        async with RedfishClient(ip, RedfishCreds(username="", password=""), timeout=timeout) as client:
            probe = await client.probe()
            return ScanHit(
                ip=ip,
                reachable=True,
                tcp_443=True,
                redfish=probe.redfish_ok or probe.error == "401 Unauthorized",
                rtt_ms=probe.rtt_ms or rtt,
                server_header=probe.server_header,
                is_hpe=_looks_like_hpe(probe.server_header),
                error=probe.error if not probe.redfish_ok else None,
            )
    except Exception as exc:  # noqa: BLE001
        return ScanHit(ip=ip, reachable=True, tcp_443=True, rtt_ms=rtt, error=str(exc))


def _looks_like_hpe(server_header: str | None) -> bool | None:
    if not server_header:
        return None
    s = server_header.lower()
    return "ilo" in s or "hewlett" in s or "hpe" in s


async def scan_cidr(
    cidr: str,
    *,
    concurrency: int = 64,
    timeout: float = 1.5,
    probe_redfish: bool = True,
) -> AsyncIterator[ScanHit]:
    """Yield :class:`ScanHit` per address as it's classified."""
    hosts = await expand_cidr(cidr)
    sem = asyncio.Semaphore(concurrency)

    async def task(ip: str) -> ScanHit:
        async with sem:
            return await _classify(ip, probe_redfish=probe_redfish, timeout=timeout)

    pending = [asyncio.create_task(task(ip)) for ip in hosts]
    for fut in asyncio.as_completed(pending):
        yield await fut
