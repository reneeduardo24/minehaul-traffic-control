from __future__ import annotations

from fastapi import Depends, FastAPI

from .auth import require_any_role
from .broker_client import publish_event
from .models import EventEnvelope, EventType, MaterialDelivery
from .persistence import connect, fetch_all, init_service_db
from .service_config import DELIVERY_SERVICE_TOKEN

app = FastAPI(title="MVTS Delivery Service")


@app.on_event("startup")
def startup() -> None:
    init_service_db("delivery")


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Delivery Service", "status": "ok"}


@app.post("/ingest/deliveries", dependencies=[Depends(require_any_role("gateway", "simulator"))])
async def create_delivery(delivery: MaterialDelivery) -> dict:
    with connect("delivery") as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO material_deliveries (id, source_event_id, vehicle_id, origin, destination, material_type, quantity_tons, delivered_at)
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
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
        event_type=EventType.DELIVERY_CREATED,
        source="delivery-service",
        payload=delivery.model_dump(mode="json"),
    )
    await publish_event(event, DELIVERY_SERVICE_TOKEN)

    with connect("delivery") as conn:
        conn.execute(
            "UPDATE material_deliveries SET source_event_id = ? WHERE id = ?",
            (event.event_id, delivery.delivery_id),
        )
        conn.commit()

    return {"accepted": True, "delivery_id": delivery.delivery_id, "event_id": event.event_id}


@app.get("/internal/deliveries", dependencies=[Depends(require_any_role("gateway", "report", "service"))])
def get_deliveries() -> dict:
    rows = fetch_all(
        "delivery",
        "SELECT id, source_event_id, vehicle_id, origin, destination, material_type, quantity_tons, delivered_at FROM material_deliveries ORDER BY delivered_at DESC",
    )
    return {"deliveries": rows}
