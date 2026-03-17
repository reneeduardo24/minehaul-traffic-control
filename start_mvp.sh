#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!
sleep 2
python scripts/vehicle_simulator.py &
SIM_PID=$!

cleanup() {
  kill "$SIM_PID" "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

python scripts/console_monitor.py watch
