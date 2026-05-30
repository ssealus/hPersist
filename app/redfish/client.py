"""Minimal async Redfish client.

Handles HTTPS quirks of iLO 4/5/6: optional Basic vs session auth, self-signed
certs, ``@odata.id`` walking with a small in-flight cache, and ``$expand``
when supported. Network errors are normalised to :class:`RedfishError`.
"""
from __future__ import annotations

import asyncio
import base64
import ssl
from dataclasses import dataclass, field
from typing import Any

import httpx


class RedfishError(Exception):
    def __init__(self, message: str, *, status: int | None = None, url: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.url = url


@dataclass(slots=True)
class RedfishCreds:
    username: str
    password: str
    tls_verify: str = "warn-only"  # strict | warn-only | off


@dataclass(slots=True)
class RedfishProbe:
    reachable: bool
    redfish_ok: bool
    server_header: str | None = None
    redfish_version: str | None = None
    error: str | None = None
    rtt_ms: float | None = None


def _ssl_context(mode: str) -> ssl.SSLContext | bool:
    if mode == "strict":
        return True
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class RedfishClient:
    """Single-host async Redfish client.

    Use as an async context manager so the underlying session is closed
    cleanly even on errors.
    """

    def __init__(self, host: str, creds: RedfishCreds, *, timeout: float = 8.0, port: int = 443) -> None:
        self.host = host
        self.port = port
        self.creds = creds
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[str, Any] = {}
        self._session_token: str | None = None
        self._session_path: str | None = None
        self._base = f"https://{host}:{port}" if port != 443 else f"https://{host}"

    async def __aenter__(self) -> "RedfishClient":
        auth_header = "Basic " + base64.b64encode(
            f"{self.creds.username}:{self.creds.password}".encode()
        ).decode()
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self.timeout,
            verify=_ssl_context(self.creds.tls_verify),
            headers={"Accept": "application/json", "Authorization": auth_header},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            if self._session_path:
                try:
                    await self._client.delete(self._session_path, headers={"X-Auth-Token": self._session_token or ""})
                except Exception:
                    pass
            await self._client.aclose()
            self._client = None

    async def probe(self) -> RedfishProbe:
        """Quick reachability + service-root probe."""
        loop = asyncio.get_event_loop()
        t0 = loop.time()
        try:
            assert self._client
            r = await self._client.get("/redfish/v1/")
            rtt = (loop.time() - t0) * 1000
            if r.status_code in (200, 401):
                data = {}
                try:
                    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                except Exception:
                    pass
                return RedfishProbe(
                    reachable=True,
                    redfish_ok=r.status_code == 200,
                    server_header=r.headers.get("server"),
                    redfish_version=data.get("RedfishVersion"),
                    error=None if r.status_code == 200 else "401 Unauthorized",
                    rtt_ms=rtt,
                )
            return RedfishProbe(reachable=True, redfish_ok=False, error=f"HTTP {r.status_code}", rtt_ms=rtt)
        except httpx.HTTPError as exc:
            return RedfishProbe(reachable=False, redfish_ok=False, error=str(exc), rtt_ms=(loop.time() - t0) * 1000)

    async def get(self, path: str, *, cache: bool = True) -> dict:
        assert self._client is not None, "use RedfishClient as an async context manager"
        if cache and path in self._cache:
            return self._cache[path]
        try:
            r = await self._client.get(path)
        except httpx.HTTPError as exc:
            raise RedfishError(str(exc), url=path) from exc
        if r.status_code >= 400:
            raise RedfishError(f"HTTP {r.status_code} on {path}", status=r.status_code, url=path)
        try:
            data = r.json()
        except Exception as exc:
            raise RedfishError(f"non-JSON response from {path}: {exc}", url=path) from exc
        if cache:
            self._cache[path] = data
        return data

    async def walk(self, root: dict, key: str) -> list[dict]:
        """Resolve a ``key`` collection on ``root`` and fetch all members."""
        ref = root.get(key)
        if not isinstance(ref, dict) or "@odata.id" not in ref:
            return []
        try:
            collection = await self.get(ref["@odata.id"])
        except RedfishError:
            return []
        members = collection.get("Members") or []
        items: list[dict] = []
        for m in members:
            url = m.get("@odata.id")
            if not url:
                continue
            try:
                items.append(await self.get(url))
            except RedfishError:
                continue
        return items
