@echo off
setlocal

set "ROOT=%~dp0"
set "PY=%ROOT%venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [start] Applying database migrations...
"%PY%" -m alembic upgrade head
if errorlevel 1 (
    echo [start] Migration failed — aborting.
    exit /b 1
)

echo [start] Launching app...
"%PY%" -m app %*
