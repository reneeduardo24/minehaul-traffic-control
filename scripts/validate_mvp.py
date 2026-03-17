from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"
UVICORN = ROOT / ".venv" / "bin" / "uvicorn"
HOST = "127.0.0.1"
PORT = int(os.getenv("MVTS_VALIDATION_PORT", "8010"))
BASE_URL = f"http://{HOST}:{PORT}"
WS_URL = f"ws://{HOST}:{PORT}/ws/events"
API_TOKEN = "mvts-demo-token"
DB_PATH = ROOT / "data" / "mvts_validation.db"
EVIDENCE_PATH = ROOT / "validation_evidence.json"
SERVICE_PORTS = {
    "MVTS_INGEST_URL": PORT + 1,
    "MVTS_TRAFFIC_LIGHT_URL": PORT + 2,
    "MVTS_CONGESTION_URL": PORT + 3,
    "MVTS_REPORT_URL": PORT + 4,
}


def wait_for_http(url: str, timeout: float = 15.0, headers: dict | None = None) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=1.0, headers=headers)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"service did not start in time: {url}")


async def change_light() -> dict:
    await asyncio.sleep(2)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        response = await client.post(
            "/api/traffic-lights/change",
            headers={"x-api-token": API_TOKEN},
            json={
                "traffic_light_id": "TL-02",
                "new_state": "GREEN",
                "changed_by": "validation-script",
            },
        )
        return response.json()


async def capture_flow(duration: float = 11.0) -> tuple[dict, list[dict], dict]:
    async with websockets.connect(WS_URL) as websocket:
        bootstrap = json.loads(await websocket.recv())
        change_task = asyncio.create_task(change_light())
        events: list[dict] = []
        end = asyncio.get_running_loop().time() + duration
        while asyncio.get_running_loop().time() < end:
            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                events.append(json.loads(raw))
            except asyncio.TimeoutError:
                continue
        light_change = await change_task
        return bootstrap, events, light_change


async def run_validation() -> dict:
    headers = {"x-api-token": API_TOKEN}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        summary_before = (await client.get("/api/reports/summary", headers=headers)).json()
    bootstrap, events, light_change = await capture_flow()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        state_after_light = (await client.get("/api/state")).json()
        summary_after = (await client.get("/api/reports/summary", headers=headers)).json()
    event_types = [event.get("event_type") for event in events]
    return {
        "base_url": BASE_URL,
        "db_path": str(DB_PATH),
        "service_ports": SERVICE_PORTS,
        "summary_before": summary_before,
        "light_change": light_change,
        "state_after_light": state_after_light,
        "summary_after": summary_after,
        "bootstrap": bootstrap,
        "events_captured": events,
        "event_types": event_types,
        "checks": {
            "service_root_ok": True,
            "ws_bootstrap_received": bool(bootstrap.get("traffic_lights")),
            "position_events_seen": "vehicle.position.updated" in event_types,
            "delivery_events_seen": "delivery.created" in event_types,
            "congestion_events_seen": "congestion.detected" in event_types,
            "traffic_light_event_seen": "traffic_light.changed" in event_types,
            "deliveries_persisted": summary_after.get("delivery_count", 0) >= 1,
            "congestion_persisted": summary_after.get("congestion_count", 0) >= 1,
            "light_state_changed": state_after_light["traffic_lights"]["TL-02"]["state"] == "GREEN",
        },
    }


def spawn(module: str, port: int, env: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [str(UVICORN), module, "--host", HOST, "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    if DB_PATH.exists():
        DB_PATH.unlink()

    env = os.environ.copy()
    env["MVTS_DB_PATH"] = str(DB_PATH)
    env["PYTHONPATH"] = str(ROOT)
    env["MVTS_BASE_URL"] = BASE_URL
    env["MVTS_GATEWAY_URL"] = BASE_URL
    env["MVTS_API_TOKEN"] = API_TOKEN
    for key, port in SERVICE_PORTS.items():
        env[key] = f"http://{HOST}:{port}"

    processes: list[subprocess.Popen] = []
    simulator = None
    try:
        processes.append(spawn("app.services_traffic_light:app", SERVICE_PORTS["MVTS_TRAFFIC_LIGHT_URL"], env))
        processes.append(spawn("app.services_congestion:app", SERVICE_PORTS["MVTS_CONGESTION_URL"], env))
        processes.append(spawn("app.services_report:app", SERVICE_PORTS["MVTS_REPORT_URL"], env))
        processes.append(spawn("app.services_ingest:app", SERVICE_PORTS["MVTS_INGEST_URL"], env))
        wait_for_http(
            f"http://{HOST}:{SERVICE_PORTS['MVTS_TRAFFIC_LIGHT_URL']}/internal/traffic-lights",
            timeout=15.0,
            headers={"x-api-token": API_TOKEN},
        )
        processes.append(spawn("app.main:app", PORT, env))
        wait_for_http(f"{BASE_URL}/", timeout=15.0)
        simulator = subprocess.Popen(
            [str(PYTHON), "scripts/vehicle_simulator.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        evidence = asyncio.run(run_validation())
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        passed = all(evidence["checks"].values())
        print(json.dumps({"passed": passed, "evidence_path": str(EVIDENCE_PATH), "checks": evidence["checks"]}, indent=2))
        return 0 if passed else 1
    finally:
        if simulator is not None:
            simulator.terminate()
            try:
                simulator.wait(timeout=5)
            except subprocess.TimeoutExpired:
                simulator.kill()
        for process in reversed(processes):
            process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    sys.exit(main())
