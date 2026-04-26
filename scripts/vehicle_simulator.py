from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models import EventType
from app.service_config import (
    BROKER_WS_URL,
    DELIVERY_URL,
    SIMULATOR_TOKEN,
    TELEMETRY_WS_URL,
    TRAFFIC_LIGHT_URL,
    bearer_headers,
)
from app.topology import ROUTE_BY_ID, VALID_FACILITY_IDS, ZONES, detect_zone_id

LOOP_DELAY_SECONDS = float(os.getenv("MVTS_SIMULATOR_LOOP_DELAY_SECONDS", "0.5"))
ZONE_SPEED_LIMITS = {zone["id"]: zone["speed_limit"] for zone in ZONES}


def build_progress_table(points: list[dict[str, float]]) -> list[float]:
    totals = [0.0]
    cumulative = 0.0
    for current, nxt in zip(points, points[1:]):
        cumulative += math.dist((current["x"], current["y"]), (nxt["x"], nxt["y"]))
        totals.append(cumulative)
    return totals


@dataclass
class VehicleRuntime:
    vehicle_id: str
    route_id: str
    material_type: str
    quantity_tons: float
    base_speed: float
    progress: float = 0.0
    has_reported_delivery: bool = False
    route: dict = field(init=False)
    progress_table: list[float] = field(init=False)

    def __post_init__(self) -> None:
        self.route = ROUTE_BY_ID[self.route_id]
        self.progress_table = build_progress_table(self.route["waypoints"])

    @property
    def origin(self) -> str:
        return self.route["origin"]

    @property
    def destination(self) -> str:
        return self.route["destination"]

    @property
    def delivery_progress(self) -> float:
        return self.progress_table[self.route["delivery_point_index"]]

    @property
    def route_length(self) -> float:
        return self.progress_table[-1]


VEHICLES = [
    VehicleRuntime("TRUCK-01", "loop_pit_a_crusher_b", "copper_ore", 24.0, 1.5, 4.2),
    VehicleRuntime("TRUCK-02", "loop_pit_b_pad_d", "waste_rock", 19.0, 1.35, 7.8),
    VehicleRuntime("TRUCK-03", "loop_ore_depot_storage", "copper_ore", 21.5, 1.4, 2.6),
    VehicleRuntime("TRUCK-04", "loop_pit_c_dump_2", "waste_rock", 17.5, 1.28, 5.1),
]


def interpolate_position(vehicle: VehicleRuntime, progress: float) -> tuple[float, float]:
    bounded = max(0.0, min(progress, vehicle.route_length))
    points = vehicle.route["waypoints"]
    for index in range(len(points) - 1):
        segment_start = vehicle.progress_table[index]
        segment_end = vehicle.progress_table[index + 1]
        if segment_start <= bounded <= segment_end:
            start = points[index]
            end = points[index + 1]
            length = max(segment_end - segment_start, 1e-6)
            ratio = (bounded - segment_start) / length
            x = start["x"] + (end["x"] - start["x"]) * ratio
            y = start["y"] + (end["y"] - start["y"]) * ratio
            return x, y
    tail = points[-1]
    return tail["x"], tail["y"]


async def fetch_traffic_lights() -> dict[str, dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{TRAFFIC_LIGHT_URL}/internal/traffic-lights",
            headers=bearer_headers(SIMULATOR_TOKEN),
        )
        response.raise_for_status()
        return response.json()["traffic_lights"]


def apply_traffic_controls(
    vehicle: VehicleRuntime,
    current_progress: float,
    desired_progress: float,
    dt: float,
    lights: dict[str, dict],
) -> tuple[float, float]:
    x, y = interpolate_position(vehicle, current_progress)
    zone_id = detect_zone_id(x, y)
    effective_speed = min(vehicle.base_speed, ZONE_SPEED_LIMITS.get(zone_id, vehicle.base_speed))
    limited_progress = min(desired_progress, vehicle.route_length)

    for control in vehicle.route.get("controls", []):
        stop_progress = vehicle.progress_table[control["stop_point_index"]]
        if not (current_progress < stop_progress <= limited_progress):
            continue
        light_state = (lights.get(control["traffic_light_id"], {}).get("state") or "GREEN").upper()
        if light_state == "RED":
            return min(current_progress, stop_progress - 0.05), 0.0
        if light_state == "YELLOW":
            effective_speed = min(effective_speed, vehicle.base_speed * 0.45)
            limited_progress = max(
                current_progress,
                min(current_progress + effective_speed * dt, stop_progress - 0.02),
            )
    return limited_progress, effective_speed


async def publish_delivery(client: httpx.AsyncClient, vehicle: VehicleRuntime) -> None:
    if vehicle.origin not in VALID_FACILITY_IDS or vehicle.destination not in VALID_FACILITY_IDS:
        raise RuntimeError("vehicle delivery endpoints must exist in topology")
    response = await client.post(
        f"{DELIVERY_URL}/ingest/deliveries",
        headers=bearer_headers(SIMULATOR_TOKEN),
        json={
            "vehicle_id": vehicle.vehicle_id,
            "origin": vehicle.origin,
            "destination": vehicle.destination,
            "material_type": vehicle.material_type,
            "quantity_tons": vehicle.quantity_tons,
        },
    )
    response.raise_for_status()


async def advance_vehicle(
    vehicle: VehicleRuntime,
    dt: float,
    lights: dict[str, dict],
    delivery_client: httpx.AsyncClient,
) -> dict:
    current_progress = vehicle.progress
    x, y = interpolate_position(vehicle, current_progress)
    zone_id = detect_zone_id(x, y)
    zone_speed = ZONE_SPEED_LIMITS.get(zone_id, vehicle.base_speed)
    desired_progress = current_progress + min(vehicle.base_speed, zone_speed) * dt
    next_progress, _ = apply_traffic_controls(vehicle, current_progress, desired_progress, dt, lights)

    vehicle.progress = min(next_progress, vehicle.route_length)
    actual_speed = max(vehicle.progress - current_progress, 0.0) / max(dt, 1e-6)

    if not vehicle.has_reported_delivery and vehicle.progress >= vehicle.delivery_progress:
        await publish_delivery(delivery_client, vehicle)
        vehicle.has_reported_delivery = True

    position_x, position_y = interpolate_position(vehicle, vehicle.progress)
    if vehicle.progress >= vehicle.route_length - 1e-6:
        vehicle.progress = 0.0
        vehicle.has_reported_delivery = False

    return {
        "vehicle_id": vehicle.vehicle_id,
        "zone_id": detect_zone_id(position_x, position_y),
        "x": round(position_x, 3),
        "y": round(position_y, 3),
        "speed": round(actual_speed, 3),
        "destination": vehicle.destination,
        "material_type": vehicle.material_type,
    }


async def telemetry_loop(traffic_lights: dict[str, dict]) -> None:
    async with httpx.AsyncClient(timeout=10.0) as delivery_client:
        while True:
            try:
                async with websockets.connect(
                    TELEMETRY_WS_URL,
                    additional_headers=bearer_headers(SIMULATOR_TOKEN),
                    ping_interval=20,
                    ping_timeout=60,
                    close_timeout=10,
                ) as telemetry_ws:
                    print("[simulator] conectado a Telemetry Service")
                    last_tick = time.monotonic()
                    while True:
                        now = time.monotonic()
                        dt = max(now - last_tick, LOOP_DELAY_SECONDS)
                        last_tick = now
                        for vehicle in VEHICLES:
                            payload = await advance_vehicle(vehicle, dt, traffic_lights, delivery_client)
                            await telemetry_ws.send(json.dumps(payload))
                        await asyncio.sleep(LOOP_DELAY_SECONDS)
            except ConnectionClosed as exc:
                print(f"[simulator] canal de telemetria cerrado: {exc}. Reintentando en 2 segundos...")
                await asyncio.sleep(2)
            except OSError as exc:
                print(f"[simulator] no fue posible conectar a Telemetry Service: {exc}. Reintentando en 2 segundos...")
                await asyncio.sleep(2)


async def traffic_light_listener(traffic_lights: dict[str, dict]) -> None:
    while True:
        try:
            async with websockets.connect(
                BROKER_WS_URL,
                additional_headers=bearer_headers(SIMULATOR_TOKEN),
                ping_interval=20,
                ping_timeout=40,
                close_timeout=10,
            ) as websocket:
                await websocket.send(json.dumps({"subscribe": [EventType.TRAFFIC_LIGHT_CHANGED.value]}))
                await websocket.recv()
                print("[simulator] suscrito a cambios de semaforo")
                while True:
                    raw = await websocket.recv()
                    event = json.loads(raw)
                    payload = event.get("payload", {})
                    traffic_lights[payload["traffic_light_id"]] = {
                        **traffic_lights.get(payload["traffic_light_id"], {}),
                        "state": payload["new_state"],
                        "zone_id": payload["zone_id"],
                        "updated_at": payload["changed_at"],
                    }
                    print(
                        f"[simulator] semaforo {payload['traffic_light_id']} actualizado a {payload['new_state']}",
                        flush=True,
                    )
        except ConnectionClosed as exc:
            print(f"[simulator] conexion al broker cerrada: {exc}. Reintentando en 2 segundos...")
            await asyncio.sleep(2)
        except OSError as exc:
            print(f"[simulator] no fue posible conectar al broker: {exc}. Reintentando en 2 segundos...")
            await asyncio.sleep(2)


async def main() -> None:
    traffic_lights = await fetch_traffic_lights()
    await asyncio.gather(telemetry_loop(traffic_lights), traffic_light_listener(traffic_lights))


if __name__ == "__main__":
    asyncio.run(main())
