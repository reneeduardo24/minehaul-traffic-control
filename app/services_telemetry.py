from __future__ import annotations

import asyncio

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect

from .auth import principal_from_websocket, require_any_role
from .broker_client import publish_event
from .models import EventEnvelope, EventType, VehiclePositionPayload
from .persistence import connect, fetch_all, init_service_db
from .service_config import TELEMETRY_SERVICE_TOKEN

app = FastAPI(title="MVTS Telemetry Service")


@app.on_event("startup")
def startup() -> None:
    init_service_db("telemetry")


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Telemetry Service", "status": "ok"}


@app.get("/internal/telemetry/positions", dependencies=[Depends(require_any_role("gateway", "congestion", "service"))])
def get_positions() -> dict:
    rows = fetch_all(
        "telemetry",
        "SELECT vehicle_id, zone_id, x, y, speed, destination, material_type, observed_at FROM latest_vehicle_positions ORDER BY vehicle_id",
    )
    return {
        "vehicle_positions": {
            row["vehicle_id"]: {
                "vehicle_id": row["vehicle_id"],
                "zone_id": row["zone_id"],
                "x": row["x"],
                "y": row["y"],
                "speed": row["speed"],
                "destination": row["destination"],
                "material_type": row["material_type"],
                "observed_at": row["observed_at"],
            }
            for row in rows
        }
    }


@app.post("/internal/telemetry/position", dependencies=[Depends(require_any_role("gateway", "simulator"))])
async def ingest_position(payload: VehiclePositionPayload) -> dict:
    await store_and_publish_position(payload)
    return {"accepted": True, "vehicle_id": payload.vehicle_id}


@app.websocket("/ingest/telemetry/ws")
async def telemetry_stream(websocket: WebSocket) -> None:
    principal = principal_from_websocket(websocket)
    if principal is None or not principal.has_any_role("simulator"):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            payload = VehiclePositionPayload.model_validate_json(raw)
            # Desacoplar el procesamiento (SQLite + HTTP al broker) del loop de
            # recepcion. Esto libera el event loop para responder pings de
            # keepalive antes de que venzan, evitando el error 1011.
            asyncio.create_task(store_and_publish_position(payload))
    except WebSocketDisconnect:
        return


async def store_and_publish_position(payload: VehiclePositionPayload) -> None:
    with connect("telemetry") as conn:
        conn.execute(
            """
            INSERT INTO latest_vehicle_positions (vehicle_id, zone_id, x, y, speed, destination, material_type, observed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vehicle_id) DO UPDATE SET
                zone_id = excluded.zone_id,
                x = excluded.x,
                y = excluded.y,
                speed = excluded.speed,
                destination = excluded.destination,
                material_type = excluded.material_type,
                observed_at = excluded.observed_at
            """,
            (
                payload.vehicle_id,
                payload.zone_id,
                payload.x,
                payload.y,
                payload.speed,
                payload.destination,
                payload.material_type,
                payload.observed_at.isoformat(),
            ),
        )
        conn.commit()

    event = EventEnvelope(
        event_type=EventType.VEHICLE_POSITION_UPDATED,
        source="telemetry-service",
        payload=payload.model_dump(mode="json"),
    )
    await publish_event(event, TELEMETRY_SERVICE_TOKEN)
