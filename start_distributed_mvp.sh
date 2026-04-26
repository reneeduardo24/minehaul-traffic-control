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

export MVTS_GATEWAY_URL="${MVTS_GATEWAY_URL:-http://127.0.0.1:8000}"
export MVTS_TELEMETRY_URL="${MVTS_TELEMETRY_URL:-http://127.0.0.1:8001}"
export MVTS_TRAFFIC_LIGHT_URL="${MVTS_TRAFFIC_LIGHT_URL:-http://127.0.0.1:8002}"
export MVTS_TRAFFIC_LIGHT_CONTROLLER_URL="${MVTS_TRAFFIC_LIGHT_CONTROLLER_URL:-http://127.0.0.1:8007}"
export MVTS_CONGESTION_URL="${MVTS_CONGESTION_URL:-http://127.0.0.1:8003}"
export MVTS_REPORT_URL="${MVTS_REPORT_URL:-http://127.0.0.1:8004}"
export MVTS_BROKER_URL="${MVTS_BROKER_URL:-http://127.0.0.1:8005}"
export MVTS_BROKER_WS_URL="${MVTS_BROKER_WS_URL:-ws://127.0.0.1:8005/internal/events/ws}"
export MVTS_DELIVERY_URL="${MVTS_DELIVERY_URL:-http://127.0.0.1:8006}"
export MVTS_TELEMETRY_WS_URL="${MVTS_TELEMETRY_WS_URL:-ws://127.0.0.1:8001/ingest/telemetry/ws}"
export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

uvicorn app.services_broker:app --host 127.0.0.1 --port 8005 &
BROKER_PID=$!
uvicorn app.services_telemetry:app --host 127.0.0.1 --port 8001 &
TELEMETRY_PID=$!
uvicorn app.services_traffic_light:app --host 127.0.0.1 --port 8002 &
TL_PID=$!
uvicorn app.services_traffic_light_controller:app --host 127.0.0.1 --port 8007 &
TL_CONTROLLER_PID=$!
uvicorn app.services_delivery:app --host 127.0.0.1 --port 8006 &
DELIVERY_PID=$!
uvicorn app.services_congestion:app --host 127.0.0.1 --port 8003 &
CONG_PID=$!
uvicorn app.services_report:app --host 127.0.0.1 --port 8004 &
REPORT_PID=$!
python -m app.report_consumer &
REPORT_CONSUMER_PID=$!
sleep 2
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
GATEWAY_PID=$!
sleep 2
python scripts/vehicle_simulator.py &
SIM_PID=$!

cleanup() {
  kill "$SIM_PID" "$GATEWAY_PID" "$REPORT_CONSUMER_PID" "$REPORT_PID" "$CONG_PID" "$DELIVERY_PID" "$TL_CONTROLLER_PID" "$TL_PID" "$TELEMETRY_PID" "$BROKER_PID" 2>/dev/null || true
}
trap cleanup EXIT

python scripts/console_monitor.py watch
