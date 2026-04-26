from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
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

SERVICE_PORTS = {
    "MVTS_TELEMETRY_URL": PORT + 1,
    "MVTS_TRAFFIC_LIGHT_URL": PORT + 2,
    "MVTS_CONGESTION_URL": PORT + 3,
    "MVTS_REPORT_URL": PORT + 4,
    "MVTS_BROKER_URL": PORT + 5,
    "MVTS_DELIVERY_URL": PORT + 6,
    "MVTS_TRAFFIC_LIGHT_CONTROLLER_URL": PORT + 7,
}

TOKENS = {
    "operator": "mvts-operator-token",
    "manager": "mvts-manager-token",
    "simulator": "mvts-simulator-token",
    "gateway": "mvts-gateway-service-token",
    "telemetry": "mvts-telemetry-service-token",
    "traffic_light": "mvts-traffic-light-service-token",
    "traffic_light_controller": "mvts-traffic-light-controller-service-token",
    "congestion": "mvts-congestion-service-token",
    "delivery": "mvts-delivery-service-token",
    "report": "mvts-report-service-token",
    "report_consumer": "mvts-report-consumer-service-token",
    "broker": "mvts-broker-service-token",
}

DB_ENV = {
    "MVTS_TELEMETRY_DB_PATH": ROOT / "data" / "telemetry.validation.db",
    "MVTS_TRAFFIC_LIGHT_DB_PATH": ROOT / "data" / "traffic_light.validation.db",
    "MVTS_CONGESTION_DB_PATH": ROOT / "data" / "congestion.validation.db",
    "MVTS_DELIVERY_DB_PATH": ROOT / "data" / "delivery.validation.db",
    "MVTS_REPORT_DB_PATH": ROOT / "data" / "report.validation.db",
}
EVIDENCE_PATH = ROOT / "validation_evidence.json"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass
class GatewayCapture:
    websocket: object
    events: list[dict]
    bootstrap: dict
    collector_task: asyncio.Task
    pinger_task: asyncio.Task


def wait_for_http(url: str, timeout: float = 20.0, headers: dict | None = None) -> None:
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


async def open_gateway_ws() -> GatewayCapture:
    websocket = await websockets.connect(WS_URL, additional_headers=bearer(TOKENS["operator"]))
    bootstrap = json.loads(await websocket.recv())
    events: list[dict] = []

    async def collector() -> None:
        while True:
            raw = await websocket.recv()
            events.append(json.loads(raw))

    async def pinger() -> None:
        while True:
            await websocket.send("ping")
            await asyncio.sleep(0.8)

    collector_task = asyncio.create_task(collector())
    pinger_task = asyncio.create_task(pinger())
    return GatewayCapture(websocket, events, bootstrap, collector_task, pinger_task)


async def close_gateway_ws(capture: GatewayCapture) -> None:
    capture.collector_task.cancel()
    capture.pinger_task.cancel()
    for task in (capture.collector_task, capture.pinger_task):
        try:
            await task
        except BaseException:
            pass
    await capture.websocket.close()


async def send_telemetry_samples() -> None:
    telemetry_ws = SERVICE_PORTS["MVTS_TELEMETRY_URL"]
    async with websockets.connect(
        f"ws://{HOST}:{telemetry_ws}/ingest/telemetry/ws",
        additional_headers=bearer(TOKENS["simulator"]),
    ) as websocket:
        slow_positions = [
            {"vehicle_id": "VAL-01", "zone_id": "Z2", "x": 10.0, "y": 4.5, "speed": 0.2, "destination": "STORAGE-DEPOT-2"},
            {"vehicle_id": "VAL-02", "zone_id": "Z2", "x": 10.6, "y": 4.5, "speed": 0.2, "destination": "DUMP-2"},
            {"vehicle_id": "VAL-03", "zone_id": "Z2", "x": 11.2, "y": 4.5, "speed": 0.2, "destination": "CRUSHER-B"},
        ]
        for payload in slow_positions:
            await websocket.send(json.dumps(payload))
        await asyncio.sleep(6)
        for payload in slow_positions:
            payload = {**payload, "x": payload["x"] + 0.1}
            await websocket.send(json.dumps(payload))
        await asyncio.sleep(1)
        fast_positions = [
            {**slow_positions[0], "speed": 2.1, "x": 10.9},
            {**slow_positions[1], "speed": 2.2, "x": 11.3},
            {**slow_positions[2], "speed": 2.0, "x": 11.7},
        ]
        for payload in fast_positions:
            await websocket.send(json.dumps(payload))
        await asyncio.sleep(1)


async def create_delivery() -> dict:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        response = await client.post(
            "/api/deliveries",
            headers=bearer(TOKENS["simulator"]),
            json={
                "vehicle_id": "VAL-01",
                "origin": "PIT-A",
                "destination": "CRUSHER-B",
                "material_type": "copper_ore",
                "quantity_tons": 25.0,
            },
        )
        response.raise_for_status()
        return response.json()


async def change_light() -> dict:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        response = await client.post(
            "/api/traffic-lights/change",
            headers=bearer(TOKENS["operator"]),
            json={
                "traffic_light_id": "TL-02",
                "new_state": "RED",
                "changed_by": "validation-script",
            },
        )
        response.raise_for_status()
        return response.json()


async def run_validation() -> dict:
    headers_operator = bearer(TOKENS["operator"])
    headers_manager = bearer(TOKENS["manager"])
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        topology = (await client.get("/api/topology", headers=headers_operator)).json()
        initial_state = (await client.get("/api/state", headers=headers_operator)).json()

    capture = await open_gateway_ws()
    try:
        light_result = await change_light()
        await create_delivery()
        await send_telemetry_samples()
        await asyncio.sleep(2)
    finally:
        await close_gateway_ws(capture)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        summary = (await client.get("/api/reports/summary", headers=headers_operator)).json()
        material_report = (await client.get("/api/reports/material", headers=headers_manager)).json()
        congestion_report = (await client.get("/api/reports/congestions", headers=headers_manager)).json()
        forbidden_report = await client.get("/api/reports/material", headers=headers_operator)
        final_state = (await client.get("/api/state", headers=headers_operator)).json()

    event_types = [item.get("event_type") for item in capture.events]
    return {
        "base_url": BASE_URL,
        "service_ports": SERVICE_PORTS,
        "topology": topology,
        "bootstrap": capture.bootstrap,
        "initial_state": initial_state,
        "final_state": final_state,
        "light_result": light_result,
        "summary": summary,
        "material_report": material_report,
        "congestion_report": congestion_report,
        "operator_material_status": forbidden_report.status_code,
        "events_captured": capture.events,
        "event_types": event_types,
        "checks": {
            "ws_bootstrap_received": capture.bootstrap.get("event_type") == "state.bootstrap",
            "position_events_seen": "vehicle.position.updated" in event_types,
            "delivery_events_seen": "delivery.created" in event_types,
            "congestion_detected_seen": "congestion.detected" in event_types,
            "congestion_cleared_seen": "congestion.cleared" in event_types,
            "traffic_light_event_seen": "traffic_light.changed" in event_types,
            "delivery_persisted": summary.get("delivery_count", 0) >= 1,
            "congestion_persisted": summary.get("congestion_count", 0) >= 1,
            "manager_report_allowed": isinstance(material_report.get("deliveries"), list),
            "operator_report_forbidden": forbidden_report.status_code == 403,
            "congestion_cleared_in_state": not final_state.get("active_congestions"),
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


def spawn_worker(module: str, env: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [str(PYTHON), "-m", module],
        cwd=ROOT,
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def main() -> int:
    for db_path in DB_ENV.values():
        if db_path.exists():
            db_path.unlink()

    env = os.environ.copy()
    env["MVTS_GATEWAY_URL"] = BASE_URL
    env["MVTS_GATEWAY_WS_URL"] = WS_URL
    for key, port in SERVICE_PORTS.items():
        env[key] = f"http://{HOST}:{port}"
    env["MVTS_BROKER_WS_URL"] = f"ws://{HOST}:{SERVICE_PORTS['MVTS_BROKER_URL']}/internal/events/ws"
    env["MVTS_TELEMETRY_WS_URL"] = f"ws://{HOST}:{SERVICE_PORTS['MVTS_TELEMETRY_URL']}/ingest/telemetry/ws"
    env["PYTHONPATH"] = str(ROOT)
    env["MVTS_OPERATOR_TOKEN"] = TOKENS["operator"]
    env["MVTS_MANAGER_TOKEN"] = TOKENS["manager"]
    env["MVTS_SIMULATOR_TOKEN"] = TOKENS["simulator"]
    env["MVTS_GATEWAY_SERVICE_TOKEN"] = TOKENS["gateway"]
    env["MVTS_TELEMETRY_SERVICE_TOKEN"] = TOKENS["telemetry"]
    env["MVTS_TRAFFIC_LIGHT_SERVICE_TOKEN"] = TOKENS["traffic_light"]
    env["MVTS_TRAFFIC_LIGHT_CONTROLLER_SERVICE_TOKEN"] = TOKENS[
        "traffic_light_controller"
    ]
    env["MVTS_CONGESTION_SERVICE_TOKEN"] = TOKENS["congestion"]
    env["MVTS_DELIVERY_SERVICE_TOKEN"] = TOKENS["delivery"]
    env["MVTS_REPORT_SERVICE_TOKEN"] = TOKENS["report"]
    env["MVTS_REPORT_CONSUMER_SERVICE_TOKEN"] = TOKENS["report_consumer"]
    env["MVTS_BROKER_SERVICE_TOKEN"] = TOKENS["broker"]
    for key, value in DB_ENV.items():
        env[key] = str(value)

    processes: list[subprocess.Popen] = []
    try:
        processes.append(spawn("app.services_broker:app", SERVICE_PORTS["MVTS_BROKER_URL"], env))
        wait_for_http(f"http://{HOST}:{SERVICE_PORTS['MVTS_BROKER_URL']}/")
        processes.append(spawn("app.services_telemetry:app", SERVICE_PORTS["MVTS_TELEMETRY_URL"], env))
        processes.append(spawn("app.services_traffic_light:app", SERVICE_PORTS["MVTS_TRAFFIC_LIGHT_URL"], env))
        processes.append(
            spawn(
                "app.services_traffic_light_controller:app",
                SERVICE_PORTS["MVTS_TRAFFIC_LIGHT_CONTROLLER_URL"],
                env,
            )
        )
        processes.append(spawn("app.services_delivery:app", SERVICE_PORTS["MVTS_DELIVERY_URL"], env))
        processes.append(spawn("app.services_congestion:app", SERVICE_PORTS["MVTS_CONGESTION_URL"], env))
        processes.append(spawn("app.services_report:app", SERVICE_PORTS["MVTS_REPORT_URL"], env))

        wait_for_http(f"http://{HOST}:{SERVICE_PORTS['MVTS_TELEMETRY_URL']}/")
        wait_for_http(f"http://{HOST}:{SERVICE_PORTS['MVTS_TRAFFIC_LIGHT_URL']}/")
        wait_for_http(
            f"http://{HOST}:{SERVICE_PORTS['MVTS_TRAFFIC_LIGHT_CONTROLLER_URL']}/"
        )
        wait_for_http(f"http://{HOST}:{SERVICE_PORTS['MVTS_CONGESTION_URL']}/")
        wait_for_http(f"http://{HOST}:{SERVICE_PORTS['MVTS_REPORT_URL']}/")
        wait_for_http(f"http://{HOST}:{SERVICE_PORTS['MVTS_DELIVERY_URL']}/")

        processes.append(spawn_worker("app.report_consumer", env))
        time.sleep(1.0)

        processes.append(spawn("app.main:app", PORT, env))
        wait_for_http(f"{BASE_URL}/")

        evidence = asyncio.run(run_validation())
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        passed = all(evidence["checks"].values())
        print(json.dumps({"passed": passed, "checks": evidence["checks"]}, indent=2))
        return 0 if passed else 1
    finally:
        for process in reversed(processes):
            process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    sys.exit(main())
