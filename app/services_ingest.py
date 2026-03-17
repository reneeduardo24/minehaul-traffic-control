from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException

from . import db
from .models import EventEnvelope, MaterialDelivery, VehiclePositionPayload
from .service_config import API_TOKEN, CONGESTION_URL, GATEWAY_URL, HEADERS

app = FastAPI(title="MVTS Ingest Service")


def require_token(x_api_token: str = Header(default="")) -> None:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.post("/internal/vehicles/position", dependencies=[Depends(require_token)])
async def ingest_vehicle_position(payload: VehiclePositionPayload) -> dict:
    position_event = EventEnvelope(
        event_type="vehicle.position.updated",
        source="vehicle-ingest-service",
        payload=payload.model_dump(mode="json"),
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        gateway_response = await client.post(f"{GATEWAY_URL}/internal/events", json=position_event.model_dump(mode="json"), headers=HEADERS)
        gateway_response.raise_for_status()
        congestion_response = await client.post(
            f"{CONGESTION_URL}/internal/evaluate",
            json={"zone_id": payload.zone_id},
            headers=HEADERS,
        )
        congestion_response.raise_for_status()
        return {
            "accepted": True,
            "congestion_event": congestion_response.json().get("event"),
        }


@app.post("/internal/deliveries", dependencies=[Depends(require_token)])
async def ingest_delivery(delivery: MaterialDelivery) -> dict:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO material_deliveries (id, vehicle_id, origin, destination, material_type, quantity_tons, delivered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                delivery.delivery_id,
                delivery.vehicle_id,
                delivery.origin,
                delivery.destination,
                delivery.material_type,
                delivery.quantity_tons,
                delivery.timestamp.isoformat(),
            ),
        )
        conn.commit()
    event = EventEnvelope(
        event_type="delivery.created",
        source="delivery-service",
        payload=delivery.model_dump(mode="json"),
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{GATEWAY_URL}/internal/events", json=event.model_dump(mode="json"), headers=HEADERS)
        response.raise_for_status()
    return {"accepted": True, "delivery_id": delivery.delivery_id}
