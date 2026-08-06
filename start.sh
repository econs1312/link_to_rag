#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------
# start.sh — Single-container entrypoint for Koyeb deploy
# Runs the ARQ worker in background and Uvicorn API in foreground.
# Handles SIGTERM / SIGINT for graceful shutdown of both processes.
# ---------------------------------------------------------------

WORKER_PID=""

cleanup() {
    echo "[start.sh] Received shutdown signal. Stopping worker (PID=${WORKER_PID})..."
    if [ -n "${WORKER_PID}" ] && kill -0 "${WORKER_PID}" 2>/dev/null; then
        kill -TERM "${WORKER_PID}"
        wait "${WORKER_PID}" 2>/dev/null || true
    fi
    echo "[start.sh] Cleanup complete."
}

trap cleanup SIGTERM SIGINT

# 1. Start ARQ worker in background
echo "[start.sh] Starting ARQ worker..."
python -m arq app.worker.WorkerSettings &
WORKER_PID=$!

# 2. Start Uvicorn API server in foreground (exec replaces this shell)
echo "[start.sh] Starting Uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
