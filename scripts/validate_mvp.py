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
PYTHON = (
    ROOT / ".venv" / "Scripts" / "python.exe"
    if os.name == "nt"
    else ROOT / ".venv" / "bin" / "python"
)
UVICORN = (
    ROOT / ".venv" / "Scripts" / "uvicorn.exe"
    if os.name == "nt"
    else ROOT / ".venv" / "bin" / "uvicorn"
)
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


async def change_light(traffic_light_id: str, new_state: str, changed_by: str) -> dict:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        response = await client.post(
            "/api/traffic-lights/change",
            headers={"x-api-token": API_TOKEN},
            json={
                "traffic_light_id": traffic_light_id,
                "new_state": new_state,
                "changed_by": changed_by,
            },
        )
        return response.json()


async def post_position(payload: dict) -> dict:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        response = await client.post(
            "/api/vehicles/position",
            headers={"x-api-token": API_TOKEN},
            json=payload,
        )
        return response.json()


async def force_congestion() -> None:
    seeded = [
        {
            "vehicle_id": "VAL-01",
            "zone_id": "Z2",
            "x": 10.0,
            "y": 4.5,
            "speed": 0.2,
            "destination": "STORAGE-DEPOT-2",
        },
        {
            "vehicle_id": "VAL-02",
            "zone_id": "Z2",
            "x": 10.6,
            "y": 4.5,
            "speed": 0.2,
            "destination": "DUMP-2",
        },
        {
            "vehicle_id": "VAL-03",
            "zone_id": "Z2",
            "x": 11.2,
            "y": 4.5,
            "speed": 0.2,
            "destination": "CRUSHER-B",
        },
    ]
    await asyncio.sleep(3)
    for payload in seeded:
        await post_position(payload)
    await asyncio.sleep(6)
    await post_position({**seeded[0], "x": 10.1, "speed": 0.1})


async def orchestrate_lights() -> dict:
    await asyncio.sleep(1)
    tl01_red = await change_light("TL-01", "RED", "validation-script")
    tl02_yellow = await change_light("TL-02", "YELLOW", "validation-script")
    tl03_red = await change_light("TL-03", "RED", "validation-script")
    tl04_yellow = await change_light("TL-04", "YELLOW", "validation-script")
    await asyncio.sleep(10)
    tl01_green = await change_light("TL-01", "GREEN", "validation-script")
    tl02_green = await change_light("TL-02", "GREEN", "validation-script")
    tl03_green = await change_light("TL-03", "GREEN", "validation-script")
    tl04_green = await change_light("TL-04", "GREEN", "validation-script")
    return {
        "tl01_red": tl01_red,
        "tl02_yellow": tl02_yellow,
        "tl03_red": tl03_red,
        "tl04_yellow": tl04_yellow,
        "tl01_green": tl01_green,
        "tl02_green": tl02_green,
        "tl03_green": tl03_green,
        "tl04_green": tl04_green,
    }


async def capture_flow(duration: float = 45.0) -> tuple[dict, list[dict], dict]:
    async with websockets.connect(
        WS_URL, additional_headers={"x-api-token": API_TOKEN}
    ) as websocket:
        bootstrap = json.loads(await websocket.recv())
        change_task = asyncio.create_task(orchestrate_lights())
        congestion_task = asyncio.create_task(force_congestion())
        events: list[dict] = []
        end = asyncio.get_running_loop().time() + duration
        while asyncio.get_running_loop().time() < end:
            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                events.append(json.loads(raw))
            except asyncio.TimeoutError:
                continue
        light_change = await change_task
        await congestion_task
        return bootstrap, events, light_change


async def run_validation() -> dict:
    headers = {"x-api-token": API_TOKEN}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        topology = (await client.get("/api/topology", headers=headers)).json()
        summary_before = (
            await client.get("/api/reports/summary", headers=headers)
        ).json()
    bootstrap, events, light_change = await capture_flow()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        state_after_light = (await client.get("/api/state", headers=headers)).json()
        summary_after = (
            await client.get("/api/reports/summary", headers=headers)
        ).json()
    event_types = [event.get("event_type") for event in events]
    return {
        "base_url": BASE_URL,
        "db_path": str(DB_PATH),
        "service_ports": SERVICE_PORTS,
        "summary_before": summary_before,
        "topology": topology,
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
            "topology_has_four_lights": len(topology.get("traffic_lights", [])) == 4,
            "topology_has_four_routes": len(topology.get("routes", [])) == 4,
            "topology_has_material_catalog": len(topology.get("materials", [])) == 2,
            "light_state_changed": all(
                state_after_light["traffic_lights"][light_id]["state"] == "GREEN"
                for light_id in ("TL-01", "TL-02", "TL-03", "TL-04")
            ),
        },
    }


def spawn(module: str, port: int, env: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [str(UVICORN), module, "--host", HOST, "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
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
        processes.append(
            spawn(
                "app.services_traffic_light:app",
                SERVICE_PORTS["MVTS_TRAFFIC_LIGHT_URL"],
                env,
            )
        )
        processes.append(
            spawn(
                "app.services_congestion:app", SERVICE_PORTS["MVTS_CONGESTION_URL"], env
            )
        )
        processes.append(
            spawn("app.services_report:app", SERVICE_PORTS["MVTS_REPORT_URL"], env)
        )
        processes.append(
            spawn("app.services_ingest:app", SERVICE_PORTS["MVTS_INGEST_URL"], env)
        )
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
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        evidence = asyncio.run(run_validation())
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        passed = all(evidence["checks"].values())
        print(
            json.dumps(
                {
                    "passed": passed,
                    "evidence_path": str(EVIDENCE_PATH),
                    "checks": evidence["checks"],
                },
                indent=2,
            )
        )
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
