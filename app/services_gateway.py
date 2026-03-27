from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect

from .gateway_state import GatewayState
from .service_config import API_TOKEN, HEADERS, INGEST_URL, REPORT_URL, TRAFFIC_LIGHT_URL

app = FastAPI(title="MVTS Gateway")
state = GatewayState()


async def require_token(x_api_token: str = Header(default="")) -> None:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


@app.on_event("startup")
async def startup() -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{TRAFFIC_LIGHT_URL}/internal/traffic-lights", headers=HEADERS)
        response.raise_for_status()
        await state.set_traffic_lights(response.json()["traffic_lights"])


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Distributed Gateway", "status": "ok"}


@app.get("/api/state", dependencies=[Depends(require_token)])
def get_state() -> dict:
    return state.snapshot()


@app.post("/api/vehicles/position", dependencies=[Depends(require_token)])
async def publish_vehicle_position(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{INGEST_URL}/internal/vehicles/position", json=payload, headers=HEADERS)
        response.raise_for_status()
        return response.json()


@app.post("/api/deliveries", dependencies=[Depends(require_token)])
async def create_delivery(delivery: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{INGEST_URL}/internal/deliveries", json=delivery, headers=HEADERS)
        response.raise_for_status()
        return response.json()


@app.post("/api/traffic-lights/change", dependencies=[Depends(require_token)])
async def change_traffic_light(command: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{TRAFFIC_LIGHT_URL}/internal/traffic-lights/change", json=command, headers=HEADERS)
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="traffic light not found")
        response.raise_for_status()
        return response.json()


@app.get("/api/reports/material", dependencies=[Depends(require_token)])
async def material_report(period: str = "day") -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{REPORT_URL}/internal/reports/material", params={"period": period}, headers=HEADERS)
        response.raise_for_status()
        return response.json()


@app.get("/api/reports/congestions", dependencies=[Depends(require_token)])
async def congestion_report() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{REPORT_URL}/internal/reports/congestions", headers=HEADERS)
        response.raise_for_status()
        return response.json()


@app.post("/internal/events", dependencies=[Depends(require_token)])
async def receive_event(event: dict) -> dict:
    await state.apply_event(event)
    return {"accepted": True}


@app.websocket("/ws/events")
async def events_ws(websocket: WebSocket) -> None:
    token = websocket.headers.get("x-api-token") or websocket.query_params.get("token")
    if token != API_TOKEN:
        await websocket.close(code=1008)
        return
        
    await state.register_connection(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in state.connections:
            state.connections.remove(websocket)
