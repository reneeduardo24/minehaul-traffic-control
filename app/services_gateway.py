from __future__ import annotations

import httpx
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from .auth import require_token
from .gateway_state import GatewayState
from .models import MaterialDelivery, TopologyResponse, TrafficLightCommand, VehiclePositionPayload
from .service_config import (
    API_TOKEN,
    HEADERS,
    INGEST_URL,
    REPORT_URL,
    TRAFFIC_LIGHT_URL,
)
from .topology import topology_payload

app = FastAPI(title="MVTS Gateway")
state = GatewayState()

# Allow the Vue dev server (and any local origin) to call the API
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
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            f"{TRAFFIC_LIGHT_URL}/internal/traffic-lights", headers=HEADERS
        )
        response.raise_for_status()
        await state.set_traffic_lights(response.json()["traffic_lights"])


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Distributed Gateway", "status": "ok"}


@app.get("/api/state", dependencies=[Depends(require_token)])
def get_state() -> dict:
    return state.snapshot()


@app.get("/api/topology", dependencies=[Depends(require_token)], response_model=TopologyResponse)
def get_topology() -> dict:
    return topology_payload()


@app.post("/api/vehicles/position", dependencies=[Depends(require_token)])
async def publish_vehicle_position(payload: VehiclePositionPayload) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{INGEST_URL}/internal/vehicles/position",
                json=payload.model_dump(mode="json"),
                headers=HEADERS,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc


@app.post("/api/deliveries", dependencies=[Depends(require_token)])
async def create_delivery(delivery: MaterialDelivery) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{INGEST_URL}/internal/deliveries",
                json=delivery.model_dump(mode="json"),
                headers=HEADERS,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc


@app.post("/api/traffic-lights/change", dependencies=[Depends(require_token)])
async def change_traffic_light(command: TrafficLightCommand) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{TRAFFIC_LIGHT_URL}/internal/traffic-lights/change",
                json=command.model_dump(mode="json"),
                headers=HEADERS,
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="traffic light not found")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc


@app.get("/api/reports/material", dependencies=[Depends(require_token)])
async def material_report(period: str = "day") -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{REPORT_URL}/internal/reports/material",
            params={"period": period},
            headers=HEADERS,
        )
        response.raise_for_status()
        return response.json()


@app.get("/api/reports/congestions", dependencies=[Depends(require_token)])
async def congestion_report() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{REPORT_URL}/internal/reports/congestions", headers=HEADERS
        )
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
