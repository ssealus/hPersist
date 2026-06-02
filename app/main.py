"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import hashlib

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import collection, exports, i18n, insight, inventories, network, servers
from app.api import settings as api_settings
from app.api import smart_hands, stats, tools, ws
from app.config import settings
from app.core.logging import prune_old_logs

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
_FRONTEND_RESOLVED = FRONTEND_DIR.resolve()


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
    insight.router,
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

_REVALIDATE_SUFFIXES = (".jsx", ".js", ".css", ".html", ".json", ".svg")


def _etag_for(path: Path) -> str:
    st = path.stat()
    return f'W/"{hashlib.md5(f"{path}-{st.st_size}-{int(st.st_mtime)}".encode()).hexdigest()}"'


def _conditional_file(request: Request, path: Path, status_code: int = 200) -> Response:
    if path.suffix.lower() not in _REVALIDATE_SUFFIXES:
        return FileResponse(path, status_code=status_code)
    etag = _etag_for(path)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
    return FileResponse(path, headers={"ETag": etag, "Cache-Control": "no-cache"}, status_code=status_code)


if FRONTEND_DIR.exists():
    static_dir = FRONTEND_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index(request: Request) -> Response:
        return _conditional_file(request, FRONTEND_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa(request: Request, full_path: str) -> Response:
        # SPA fallback: real asset wins, otherwise serve index.html
        if full_path.startswith(("api/", "ws/", "static/")):
            return _conditional_file(request, FRONTEND_DIR / "index.html", status_code=404)
        try:
            candidate = (FRONTEND_DIR / full_path).resolve()
            candidate.relative_to(_FRONTEND_RESOLVED)
        except (ValueError, OSError):
            return _conditional_file(request, FRONTEND_DIR / "index.html")
        if candidate.is_file():
            return _conditional_file(request, candidate)
        return _conditional_file(request, FRONTEND_DIR / "index.html")
