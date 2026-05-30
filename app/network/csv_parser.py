"""CSV inventory parser.

Schema (header row required, case-insensitive)::

    ip, hostname, login, password

``hostname`` is optional — empty cells are accepted. Every row is validated:
IPv4 shape, missing credentials, duplicate IPs. Each row's status is
``ok | warn | err``. The caller decides what to do with warnings; ``err`` rows
block the collection.
"""
from __future__ import annotations

import csv
import io
import ipaddress
from dataclasses import dataclass, field


@dataclass(slots=True)
class ParsedRow:
    line: int
    ip: str
    hostname: str | None
    login: str
    password: str
    status: str = "ok"
    message: str | None = None


@dataclass(slots=True)
class ParseReport:
    rows: list[ParsedRow] = field(default_factory=list)
    fatal: list[str] = field(default_factory=list)

    @property
    def ok_rows(self) -> list[ParsedRow]:
        return [r for r in self.rows if r.status == "ok"]

    @property
    def err_rows(self) -> list[ParsedRow]:
        return [r for r in self.rows if r.status == "err"]

    def summary(self) -> dict:
        return {
            "total": len(self.rows),
            "ok": sum(1 for r in self.rows if r.status == "ok"),
            "warn": sum(1 for r in self.rows if r.status == "warn"),
            "err": sum(1 for r in self.rows if r.status == "err"),
            "fatal": list(self.fatal),
        }


REQUIRED = {"ip", "login", "password"}
OPTIONAL = {"hostname"}


def parse_csv(text: str) -> ParseReport:
    report = ParseReport()
    try:
        reader = csv.DictReader(io.StringIO(text))
    except Exception as exc:  # noqa: BLE001
        report.fatal.append(f"could not parse CSV: {exc}")
        return report

    if not reader.fieldnames:
        report.fatal.append("empty CSV — no header row")
        return report

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = REQUIRED - headers
    if missing:
        report.fatal.append(f"missing required columns: {', '.join(sorted(missing))}")
        return report

    seen_ips: set[str] = set()
    for line_idx, raw in enumerate(reader, start=2):  # header was line 1
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        ip = row.get("ip", "")
        hostname = row.get("hostname") or None
        login = row.get("login", "")
        password = row.get("password", "")

        item = ParsedRow(line=line_idx, ip=ip, hostname=hostname, login=login, password=password)

        if not ip:
            item.status = "err"
            item.message = "missing IP"
            report.rows.append(item)
            continue
        try:
            ipaddress.IPv4Address(ip)
        except ValueError:
            item.status = "err"
            item.message = "invalid IPv4"
            report.rows.append(item)
            continue
        if ip in seen_ips:
            item.status = "warn"
            item.message = "duplicate IP — earlier row wins"
        seen_ips.add(ip)

        if not login:
            item.status = "err"
            item.message = "missing login"
            report.rows.append(item)
            continue
        if not password:
            item.status = "err"
            item.message = "missing password"
            report.rows.append(item)
            continue

        report.rows.append(item)

    return report


def template_csv() -> str:
    """Return the CSV template shipped to remote engineers."""
    return (
        "ip,hostname,login,password\n"
        "# Fill in one host per line. ip + login + password are required.\n"
        "# hostname is optional; leave blank to derive from iLO.\n"
        "10.0.0.10,dl380-fra-01,Administrator,changeMe\n"
    )
