from __future__ import annotations

import asyncio
import os
from itertools import cycle

import httpx

API_TOKEN = os.getenv("MVTS_API_TOKEN", "mvts-demo-token")
BASE_URL = os.getenv("MVTS_BASE_URL", "http://127.0.0.1:8000")
HEADERS = {"x-api-token": API_TOKEN}

VEHICLES = [
    {
        "vehicle_id": "TRUCK-01",
        "destination": "CRUSHER-A",
        "origin": "PIT-1",
        "material_type": "copper_ore",
        "quantity_tons": 20.0,
        "route": cycle(
            [
                {"zone_id": "Z1", "x": 0, "y": 0, "speed": 2.2},
                {"zone_id": "Z2", "x": 10, "y": 3, "speed": 0.4},
                {"zone_id": "Z2", "x": 11, "y": 3, "speed": 0.3},
                {"zone_id": "Z2", "x": 12, "y": 4, "speed": 0.2},
                {"zone_id": "Z2", "x": 12.5, "y": 4, "speed": 0.2},
                {"zone_id": "Z2", "x": 13, "y": 4, "speed": 0.3},
                {"zone_id": "Z2", "x": 13.5, "y": 4, "speed": 0.4},
                {"zone_id": "Z3", "x": 20, "y": 5, "speed": 2.5},
            ]
        ),
    },
    {
        "vehicle_id": "TRUCK-02",
        "destination": "CRUSHER-A",
        "origin": "PIT-2",
        "material_type": "copper_ore",
        "quantity_tons": 22.5,
        "route": cycle(
            [
                {"zone_id": "Z1", "x": 1, "y": 1, "speed": 2.0},
                {"zone_id": "Z2", "x": 10, "y": 2, "speed": 0.5},
                {"zone_id": "Z2", "x": 11, "y": 2, "speed": 0.6},
                {"zone_id": "Z2", "x": 12, "y": 2, "speed": 0.4},
                {"zone_id": "Z2", "x": 12.5, "y": 2, "speed": 0.4},
                {"zone_id": "Z2", "x": 13, "y": 2, "speed": 0.5},
                {"zone_id": "Z2", "x": 13.5, "y": 2, "speed": 0.4},
                {"zone_id": "Z3", "x": 21, "y": 5, "speed": 2.4},
            ]
        ),
    },
    {
        "vehicle_id": "TRUCK-03",
        "destination": "CRUSHER-A",
        "origin": "PIT-3",
        "material_type": "waste_rock",
        "quantity_tons": 18.0,
        "route": cycle(
            [
                {"zone_id": "Z1", "x": 2, "y": 2, "speed": 2.1},
                {"zone_id": "Z2", "x": 10, "y": 1, "speed": 0.4},
                {"zone_id": "Z2", "x": 11, "y": 1, "speed": 0.4},
                {"zone_id": "Z2", "x": 12, "y": 1, "speed": 0.3},
                {"zone_id": "Z2", "x": 12.5, "y": 1, "speed": 0.3},
                {"zone_id": "Z2", "x": 13, "y": 1, "speed": 0.4},
                {"zone_id": "Z2", "x": 13.5, "y": 1, "speed": 0.4},
                {"zone_id": "Z3", "x": 22, "y": 5, "speed": 2.2},
            ]
        ),
    },
]


async def post_position(client: httpx.AsyncClient, vehicle: dict, step: dict) -> None:
    payload = {
        "vehicle_id": vehicle["vehicle_id"],
        "zone_id": step["zone_id"],
        "x": step["x"],
        "y": step["y"],
        "speed": step["speed"],
        "destination": vehicle["destination"],
    }
    await client.post("/api/vehicles/position", json=payload, headers=HEADERS)
    if step["zone_id"] == "Z3":
        delivery = {
            "vehicle_id": vehicle["vehicle_id"],
            "origin": vehicle["origin"],
            "destination": vehicle["destination"],
            "material_type": vehicle["material_type"],
            "quantity_tons": vehicle["quantity_tons"],
        }
        await client.post("/api/deliveries", json=delivery, headers=HEADERS)


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        while True:
            for vehicle in VEHICLES:
                step = next(vehicle["route"])
                await post_position(client, vehicle, step)
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
