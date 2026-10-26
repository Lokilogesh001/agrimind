#!/usr/bin/env bash
# AgriMind Unified Application Launcher (Linux / macOS)
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="${SCRIPT_DIR}/web"

echo -e "\033[36m[AgriMind] Discovering Python environment...\033[0m"

# Discover Python / venv
PYTHON_EXE=""
if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON_EXE="$VIRTUAL_ENV/bin/python"
elif [ -x "${SCRIPT_DIR}/.venv/bin/python" ]; then
    PYTHON_EXE="${SCRIPT_DIR}/.venv/bin/python"
elif [ -x "${SCRIPT_DIR}/venv/bin/python" ]; then
    PYTHON_EXE="${SCRIPT_DIR}/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_EXE="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_EXE="$(command -v python)"
fi

if [ -z "$PYTHON_EXE" ]; then
    echo -e "\033[31m[AgriMind] ERROR: Python 3 was not found. Please install Python 3.10+.\033[0m"
    exit 1
fi

echo -e "\033[36m[AgriMind] Using Python: ${PYTHON_EXE}\033[0m"

# Verify dependencies
$PYTHON_EXE -c "import fastapi, uvicorn" 2>/dev/null || {
    echo -e "\033[33m[AgriMind] Dependencies missing. Installing from requirements.txt...\033[0m"
    $PYTHON_EXE -m pip install -r "${SCRIPT_DIR}/requirements.txt"
}

# Check frontend
if [ ! -d "${WEB_DIR}/node_modules" ]; then
    echo -e "\033[33m[AgriMind] Frontend node_modules missing. Running npm install...\033[0m"
    (cd "$WEB_DIR" && npm install)
fi

echo -e "\033[32m[AgriMind] Starting backend on http://127.0.0.1:8000...\033[0m"
$PYTHON_EXE -m uvicorn api.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo -e "\033[32m[AgriMind] Starting frontend on http://localhost:3000...\033[0m"
(cd "$WEB_DIR" && npm run dev) &
FRONTEND_PID=$!

cleanup() {
    echo -e "\n\033[36m[AgriMind] Shutting down services...\033[0m"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    echo -e "\033[32m[AgriMind] All services stopped cleanly.\033[0m"
}

trap cleanup SIGINT SIGTERM EXIT

echo -e "\033[36m[AgriMind] Both services running. Press Ctrl+C to terminate.\033[0m"
wait
