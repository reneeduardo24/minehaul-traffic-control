from __future__ import annotations

import asyncio
import math
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.topology import ROUTE_BY_ID, VALID_FACILITY_IDS, ZONES, detect_zone_id

API_TOKEN = os.getenv("MVTS_API_TOKEN", "mvts-demo-token")
BASE_URL = os.getenv("MVTS_BASE_URL", "http://127.0.0.1:8000")
HEADERS = {"x-api-token": API_TOKEN}
LOOP_DELAY_SECONDS = 0.25

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
    VehicleRuntime(
        vehicle_id="TRUCK-01",
        route_id="loop_pit_a_crusher_b",
        material_type="copper_ore",
        quantity_tons=24.0,
        base_speed=1.5,
        progress=4.2,
    ),
    VehicleRuntime(
        vehicle_id="TRUCK-02",
        route_id="loop_pit_b_pad_d",
        material_type="waste_rock",
        quantity_tons=19.0,
        base_speed=1.35,
        progress=7.8,
    ),
    VehicleRuntime(
        vehicle_id="TRUCK-03",
        route_id="loop_ore_depot_storage",
        material_type="copper_ore",
        quantity_tons=21.5,
        base_speed=1.4,
        progress=2.6,
    ),
    VehicleRuntime(
        vehicle_id="TRUCK-04",
        route_id="loop_pit_c_dump_2",
        material_type="waste_rock",
        quantity_tons=17.5,
        base_speed=1.28,
        progress=5.1,
    ),
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


async def fetch_state(client: httpx.AsyncClient) -> dict:
    response = await client.get("/api/state", headers=HEADERS)
    response.raise_for_status()
    return response.json()


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


async def publish_position(client: httpx.AsyncClient, vehicle: VehicleRuntime, speed: float) -> None:
    x, y = interpolate_position(vehicle, vehicle.progress)
    payload = {
        "vehicle_id": vehicle.vehicle_id,
        "zone_id": detect_zone_id(x, y),
        "x": round(x, 3),
        "y": round(y, 3),
        "speed": round(speed, 3),
        "destination": vehicle.destination,
        "material_type": vehicle.material_type,
    }
    response = await client.post("/api/vehicles/position", json=payload, headers=HEADERS)
    response.raise_for_status()


async def publish_delivery(client: httpx.AsyncClient, vehicle: VehicleRuntime) -> None:
    if vehicle.origin not in VALID_FACILITY_IDS or vehicle.destination not in VALID_FACILITY_IDS:
        raise RuntimeError("vehicle delivery endpoints must exist in topology")
    delivery = {
        "vehicle_id": vehicle.vehicle_id,
        "origin": vehicle.origin,
        "destination": vehicle.destination,
        "material_type": vehicle.material_type,
        "quantity_tons": vehicle.quantity_tons,
    }
    response = await client.post("/api/deliveries", json=delivery, headers=HEADERS)
    response.raise_for_status()


async def advance_vehicle(client: httpx.AsyncClient, vehicle: VehicleRuntime, dt: float, lights: dict[str, dict]) -> None:
    current_progress = vehicle.progress
    x, y = interpolate_position(vehicle, current_progress)
    zone_id = detect_zone_id(x, y)
    zone_speed = ZONE_SPEED_LIMITS.get(zone_id, vehicle.base_speed)
    desired_progress = current_progress + min(vehicle.base_speed, zone_speed) * dt
    next_progress, _ = apply_traffic_controls(vehicle, current_progress, desired_progress, dt, lights)

    vehicle.progress = min(next_progress, vehicle.route_length)
    actual_speed = max(vehicle.progress - current_progress, 0.0) / max(dt, 1e-6)

    if not vehicle.has_reported_delivery and vehicle.progress >= vehicle.delivery_progress:
        await publish_delivery(client, vehicle)
        vehicle.has_reported_delivery = True

    await publish_position(client, vehicle, actual_speed)

    if vehicle.progress >= vehicle.route_length - 1e-6:
        vehicle.progress = 0.0
        vehicle.has_reported_delivery = False


async def simulate_tick(client: httpx.AsyncClient, dt: float) -> None:
    state = await fetch_state(client)
    lights = state.get("traffic_lights", {})
    await asyncio.gather(*(advance_vehicle(client, vehicle, dt, lights) for vehicle in VEHICLES))


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        last_tick = time.monotonic()
        while True:
            now = time.monotonic()
            dt = max(now - last_tick, LOOP_DELAY_SECONDS)
            last_tick = now
            await simulate_tick(client, dt)
            await asyncio.sleep(LOOP_DELAY_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
