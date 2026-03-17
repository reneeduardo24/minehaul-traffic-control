from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime

import httpx
import websockets

BASE_URL = os.getenv("MVTS_BASE_URL", "http://127.0.0.1:8000")
WS_URL = os.getenv("MVTS_WS_URL", "ws://127.0.0.1:8000/ws/events")
API_TOKEN = os.getenv("MVTS_API_TOKEN", "mvts-demo-token")


def now() -> str:
    return datetime.utcnow().strftime("%H:%M:%S")


async def watch() -> None:
    async with websockets.connect(WS_URL) as websocket:
        bootstrap = json.loads(await websocket.recv())
        print(f"[{now()}] conectado al monitor MVTS")
        print(json.dumps(bootstrap, indent=2))
        while True:
            await websocket.send("ping")
            raw = await websocket.recv()
            event = json.loads(raw)
            print(f"[{now()}] {event['event_type']} -> {json.dumps(event['payload'])}")
            await asyncio.sleep(1)


async def change_light(traffic_light_id: str, new_state: str, changed_by: str) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        response = await client.post(
            "/api/traffic-lights/change",
            headers={"x-api-token": API_TOKEN},
            json={
                "traffic_light_id": traffic_light_id,
                "new_state": new_state,
                "changed_by": changed_by,
            },
        )
        print(response.json())


async def summary() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        response = await client.get("/api/reports/summary", headers={"x-api-token": API_TOKEN})
        print(json.dumps(response.json(), indent=2))


async def main() -> None:
    parser = argparse.ArgumentParser(description="MVTS console monitor")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("watch")

    change = subparsers.add_parser("change-light")
    change.add_argument("traffic_light_id")
    change.add_argument("new_state")
    change.add_argument("--by", default="central-operator")

    subparsers.add_parser("summary")
    args = parser.parse_args()

    if args.command == "watch":
        await watch()
    elif args.command == "change-light":
        await change_light(args.traffic_light_id, args.new_state, args.by)
    elif args.command == "summary":
        await summary()


if __name__ == "__main__":
    asyncio.run(main())
