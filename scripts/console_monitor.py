from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

from app.service_config import GATEWAY_URL, GATEWAY_WS_URL, MANAGER_TOKEN, OPERATOR_TOKEN, bearer_headers


def now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def token_for_actor(actor: str) -> str:
    return MANAGER_TOKEN if actor == "manager" else OPERATOR_TOKEN


async def watch(actor: str) -> None:
    while True:
        try:
            async with websockets.connect(
                GATEWAY_WS_URL,
                additional_headers=bearer_headers(token_for_actor(actor)),
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
                max_queue=512,
            ) as websocket:
                bootstrap = json.loads(await websocket.recv())
                print(f"[{now()}] conectado al monitor MVTS como {actor}")
                print(json.dumps(bootstrap, indent=2))
                while True:
                    raw = await websocket.recv()
                    event = json.loads(raw)
                    print(f"[{now()}] {event['event_type']} -> {json.dumps(event['payload'])}")
        except ConnectionClosed as exc:
            print(f"[{now()}] monitor desconectado: {exc}. Reintentando en 2 segundos...")
            await asyncio.sleep(2)
        except OSError as exc:
            print(f"[{now()}] no fue posible conectar al gateway: {exc}. Reintentando en 2 segundos...")
            await asyncio.sleep(2)


async def change_light(actor: str, traffic_light_id: str, new_state: str, changed_by: str) -> None:
    async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=5.0) as client:
        response = await client.post(
            "/api/traffic-lights/change",
            headers=bearer_headers(token_for_actor(actor)),
            json={
                "traffic_light_id": traffic_light_id,
                "new_state": new_state,
                "changed_by": changed_by,
            },
        )
        print(response.status_code)
        print(response.text)


async def summary(actor: str) -> None:
    async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=5.0) as client:
        response = await client.get(
            "/api/reports/summary", headers=bearer_headers(token_for_actor(actor))
        )
        print(response.status_code)
        print(json.dumps(response.json(), indent=2))


async def material_report(actor: str, period: str) -> None:
    async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=5.0) as client:
        response = await client.get(
            "/api/reports/material",
            params={"period": period},
            headers=bearer_headers(token_for_actor(actor)),
        )
        print(response.status_code)
        print(response.text)


async def congestions_report(actor: str) -> None:
    async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=5.0) as client:
        response = await client.get(
            "/api/reports/congestions", headers=bearer_headers(token_for_actor(actor))
        )
        print(response.status_code)
        print(response.text)


async def main() -> None:
    parser = argparse.ArgumentParser(description="MVTS console monitor")
    parser.add_argument("--actor", choices=["operator", "manager"], default=os.getenv("MVTS_MONITOR_ACTOR", "operator"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("watch")

    change = subparsers.add_parser("change-light")
    change.add_argument("traffic_light_id")
    change.add_argument("new_state")
    change.add_argument("--by", default="central-operator")

    subparsers.add_parser("summary")

    material = subparsers.add_parser("report-material")
    material.add_argument("period", choices=["day", "week", "month"])

    subparsers.add_parser("report-congestions")

    args = parser.parse_args()
    actor = args.actor

    if args.command == "watch":
        await watch(actor)
    elif args.command == "change-light":
        await change_light(actor, args.traffic_light_id, args.new_state, args.by)
    elif args.command == "summary":
        await summary(actor)
    elif args.command == "report-material":
        await material_report(actor, args.period)
    elif args.command == "report-congestions":
        await congestions_report(actor)


if __name__ == "__main__":
    asyncio.run(main())
