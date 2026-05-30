"""Shared Pydantic models for request/response bodies."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Problem(BaseModel):
    detail: str
    code: str | None = None
    extra: dict[str, Any] | None = None


class HostSpecIn(BaseModel):
    ip: str
    hostname: str | None = None
    login: str
    password: str


class CollectionStart(BaseModel):
    name: str
    organization: str | None = None
    description: str | None = None
    created_by: str | None = None
    mode: str = Field(pattern="^(cidr|csv)$")
    cidr: str | None = None
    hosts: list[HostSpecIn] | None = None
    default_login: str | None = None
    default_password: str | None = None
    concurrency: int | None = None
    timeout: float | None = None


class SmartHandsGenerate(BaseModel):
    name: str
    organization: str | None = None
    description: str | None = None
    created_by: str | None = None
    csv_text: str | None = None


class RedfishTestRequest(BaseModel):
    host: str
    method: str = "GET"
    path: str = "/redfish/v1/"
    username: str = ""
    password: str = ""
    body: dict[str, Any] | None = None
    tls: str = "warn-only"
    timeout: float = 8.0
    port: int = 443


class ExportRequest(BaseModel):
    inventory_ids: list[str]
    format: str = Field(pattern="^(xlsx|csv|json)$")
    layout: str = "flat"
    groups: list[str] | None = None
    include_columns: list[str] | None = None
    anonymize: bool = False
