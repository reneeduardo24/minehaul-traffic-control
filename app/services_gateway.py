from __future__ import annotations

import asyncio
import contextlib

import httpx
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .auth import principal_from_websocket, require_any_role
from .broker_client import run_subscription_loop
from .gateway_state import GatewayConnectionManager
from .models import EventEnvelope, EventType, MaterialDelivery, TopologyResponse, TrafficLightCommand, VehiclePositionPayload
from .service_config import (
    CONGESTION_URL,
    DELIVERY_URL,
    GATEWAY_SERVICE_TOKEN,
    REPORT_URL,
    TELEMETRY_URL,
    TRAFFIC_LIGHT_CONTROLLER_URL,
    TRAFFIC_LIGHT_URL,
    bearer_headers,
)
from .topology import topology_payload

app = FastAPI(title="MVTS Gateway")
connections = GatewayConnectionManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    app.state.subscription_task = asyncio.create_task(subscribe_to_broker_events())


@app.on_event("shutdown")
async def shutdown() -> None:
    task = getattr(app.state, "subscription_task", None)
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Distributed Gateway", "status": "ok"}


@app.get("/api/state", dependencies=[Depends(require_any_role("operator", "manager"))])
async def get_state() -> dict:
    return await compose_operational_state()


@app.get("/api/topology", dependencies=[Depends(require_any_role("operator", "manager"))], response_model=TopologyResponse)
def get_topology() -> dict:
    return topology_payload()


@app.post("/api/vehicles/position", dependencies=[Depends(require_any_role("simulator"))])
async def publish_vehicle_position(payload: VehiclePositionPayload) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{TELEMETRY_URL}/internal/telemetry/position",
            json=payload.model_dump(mode="json"),
            headers=bearer_headers(GATEWAY_SERVICE_TOKEN),
        )
        response.raise_for_status()
        return response.json()


@app.post("/api/deliveries", dependencies=[Depends(require_any_role("simulator"))])
async def create_delivery(delivery: MaterialDelivery) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{DELIVERY_URL}/ingest/deliveries",
            json=delivery.model_dump(mode="json"),
            headers=bearer_headers(GATEWAY_SERVICE_TOKEN),
        )
        response.raise_for_status()
        return response.json()


@app.post("/api/traffic-lights/change", dependencies=[Depends(require_any_role("operator"))])
async def change_traffic_light(command: TrafficLightCommand) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{TRAFFIC_LIGHT_CONTROLLER_URL}/internal/traffic-lights/change",
            json=command.model_dump(mode="json"),
            headers=bearer_headers(GATEWAY_SERVICE_TOKEN),
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="traffic light not found")
        response.raise_for_status()
        return response.json()


@app.get("/api/reports/summary", dependencies=[Depends(require_any_role("operator", "manager"))])
async def summary_report() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{REPORT_URL}/internal/reports/summary",
            headers=bearer_headers(GATEWAY_SERVICE_TOKEN),
        )
        response.raise_for_status()
        return response.json()


@app.get("/api/reports/material", dependencies=[Depends(require_any_role("manager"))])
async def material_report(period: str = "day") -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{REPORT_URL}/internal/reports/material",
            params={"period": period},
            headers=bearer_headers(GATEWAY_SERVICE_TOKEN),
        )
        response.raise_for_status()
        return response.json()


@app.get("/api/reports/congestions", dependencies=[Depends(require_any_role("manager"))])
async def congestion_report() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{REPORT_URL}/internal/reports/congestions",
            headers=bearer_headers(GATEWAY_SERVICE_TOKEN),
        )
        response.raise_for_status()
        return response.json()


@app.websocket("/ws/events")
async def events_ws(websocket: WebSocket) -> None:
    principal = principal_from_websocket(websocket)
    if principal is None or not principal.has_any_role("operator", "manager"):
        await websocket.close(code=1008)
        return

    bootstrap = await compose_operational_state()
    await connections.register(websocket, bootstrap)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await connections.unregister(websocket)


async def compose_operational_state() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        telemetry_task = client.get(
            f"{TELEMETRY_URL}/internal/telemetry/positions",
            headers=bearer_headers(GATEWAY_SERVICE_TOKEN),
        )
        lights_task = client.get(
            f"{TRAFFIC_LIGHT_URL}/internal/traffic-lights",
            headers=bearer_headers(GATEWAY_SERVICE_TOKEN),
        )
        congestion_task = client.get(
            f"{CONGESTION_URL}/internal/congestion/active",
            headers=bearer_headers(GATEWAY_SERVICE_TOKEN),
        )
        telemetry_response, lights_response, congestion_response = await asyncio.gather(
            telemetry_task,
            lights_task,
            congestion_task,
        )
        telemetry_response.raise_for_status()
        lights_response.raise_for_status()
        congestion_response.raise_for_status()
        return {
            "vehicle_positions": telemetry_response.json()["vehicle_positions"],
            "traffic_lights": lights_response.json()["traffic_lights"],
            "active_congestions": congestion_response.json()["active_congestions"],
        }


async def subscribe_to_broker_events() -> None:
    await run_subscription_loop(
        subscriber_name="gateway",
        token=GATEWAY_SERVICE_TOKEN,
        event_types=[
            EventType.VEHICLE_POSITION_UPDATED,
            EventType.TRAFFIC_LIGHT_CHANGED,
            EventType.DELIVERY_CREATED,
            EventType.CONGESTION_DETECTED,
            EventType.CONGESTION_CLEARED,
        ],
        handler=forward_broker_event,
    )


async def forward_broker_event(event: EventEnvelope) -> None:
    await connections.broadcast(event.model_dump(mode="json"))
