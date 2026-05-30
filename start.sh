#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${ROOT}/venv/bin/python"
[[ -x "$PY" ]] || PY="python"

echo "[start] Applying database migrations..."
"$PY" -m alembic upgrade head

echo "[start] Launching app..."
exec "$PY" -m app "$@"
