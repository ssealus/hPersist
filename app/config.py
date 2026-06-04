"""Settings — env-driven via pydantic-settings.

Prefix `HPERSIST_`, nested groups joined with `__`
(`HPERSIST_DB__URL`, `HPERSIST_COLLECTOR__CONCURRENCY`, etc).
Full list with defaults: see `.env.example` at the project root.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    log_level: Literal["critical", "error", "warning", "info", "debug", "trace"] = "info"
    reload: bool = False


class DatabaseSettings(BaseModel):
    url: str | None = None
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout_seconds: float = 30.0
    pool_recycle_seconds: int = 1800
    echo: bool = False

    # SQLite-only; ignored on Postgres
    sqlite_journal_mode: Literal["WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"] = "WAL"
    sqlite_synchronous: Literal["OFF", "NORMAL", "FULL", "EXTRA"] = "NORMAL"
    sqlite_busy_timeout_ms: int = 15000
    sqlite_foreign_keys: bool = True


class CollectorSettings(BaseModel):
    concurrency: int = 16
    timeout_seconds: float = 8.0
    tls_verify: Literal["strict", "warn-only", "off"] = "warn-only"


class LogSettings(BaseModel):
    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    retention_days: int = 90


class CORSSettings(BaseModel):
    allow_origins: list[str] = ["*"]
    allow_credentials: bool = False
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HPERSIST_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "prod", "test"] = "dev"

    data_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data"
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    collector: CollectorSettings = Field(default_factory=CollectorSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)

    # build-time constants, kept here so /health and /version don't have to
    # round-trip through app.__init__
    schema_version: str = "hpersist/v1"
    collector_version: str = "0.4.2"

    def resolve(self) -> Settings:
        self.data_dir = self.data_dir.expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
        (self.data_dir / "archives").mkdir(exist_ok=True)
        (self.data_dir / "uploads").mkdir(exist_ok=True)
        if not self.db.url:
            self.db.url = f"sqlite:///{self.data_dir / 'hpersist.db'}"
        return self


settings = Settings().resolve()
