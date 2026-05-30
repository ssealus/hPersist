"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import collection, exports, i18n, inventories, network, servers
from app.api import settings as api_settings
from app.api import smart_hands, stats, tools, ws
from app.config import settings
from app.core.logging import prune_old_logs

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # migrations run in start.sh before uvicorn; here we just assume head
    settings.resolve()
    prune_old_logs(days=settings.log.retention_days)
    yield


app = FastAPI(
    title="hPersist",
    version=__version__,
    description="HPE iLO Redfish inventory collector — local and Smart Hands modes.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
)


API_PREFIX = "/api/v1"
for router in (
    inventories.router,
    servers.router,
    collection.router,
    smart_hands.router,
    network.router,
    tools.router,
    exports.router,
    stats.router,
    i18n.router,
    api_settings.router,
):
    app.include_router(router, prefix=API_PREFIX)

# WS is unversioned — lives at /ws/...
app.include_router(ws.router)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "schema": settings.schema_version}


@app.get("/api/v1/version")
def version() -> dict:
    return {"version": __version__, "collector": settings.collector_version}


if FRONTEND_DIR.exists():
    static_dir = FRONTEND_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        # SPA fallback: real asset wins, otherwise serve index.html
        if full_path.startswith(("api/", "ws/", "static/")):
            return FileResponse(FRONTEND_DIR / "index.html", status_code=404)
        candidate = FRONTEND_DIR / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIR / "index.html")
