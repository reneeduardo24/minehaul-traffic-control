from __future__ import annotations

from collections import Counter

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect

from . import db
from .models import MaterialDelivery, TrafficLightCommand, VehiclePositionPayload
from .state import AppState

API_TOKEN = "mvts-demo-token"
app = FastAPI(title="MVTS MVP")
state = AppState()


def require_token(x_api_token: str = Header(default="")) -> None:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    state.seed_traffic_lights()


@app.get("/")
def root() -> dict:
    return {"name": "MVTS MVP", "status": "ok"}


@app.get("/api/state")
def get_state() -> dict:
    return state.snapshot()


@app.post("/api/vehicles/position", dependencies=[Depends(require_token)])
async def publish_vehicle_position(payload: VehiclePositionPayload) -> dict:
    congestion_event = await state.handle_vehicle_position(payload)
    return {"accepted": True, "congestion_event": congestion_event.model_dump(mode="json") if congestion_event else None}


@app.post("/api/deliveries", dependencies=[Depends(require_token)])
async def create_delivery(delivery: MaterialDelivery) -> dict:
    await state.handle_delivery(delivery)
    return {"accepted": True, "delivery_id": delivery.delivery_id}


@app.post("/api/traffic-lights/change", dependencies=[Depends(require_token)])
async def change_traffic_light(command: TrafficLightCommand) -> dict:
    if command.traffic_light_id not in state.traffic_lights:
        raise HTTPException(status_code=404, detail="traffic light not found")
    event = await state.handle_traffic_light_command(command)
    return {"accepted": True, "event": event.model_dump(mode="json")}


@app.get("/api/reports/summary", dependencies=[Depends(require_token)])
def summary_report() -> dict:
    deliveries = db.fetch_all("SELECT * FROM material_deliveries ORDER BY delivered_at DESC")
    congestions = db.fetch_all("SELECT * FROM congestion_events ORDER BY created_at DESC")
    by_material = Counter(row["material_type"] for row in deliveries)
    return {
        "delivery_count": len(deliveries),
        "congestion_count": len(congestions),
        "tons_total": round(sum(row["quantity_tons"] for row in deliveries), 2),
        "deliveries_by_material": dict(by_material),
        "latest_congestion": congestions[0] if congestions else None,
    }


@app.websocket("/ws/events")
async def events_ws(websocket: WebSocket) -> None:
    await state.register_connection(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in state.connections:
            state.connections.remove(websocket)
