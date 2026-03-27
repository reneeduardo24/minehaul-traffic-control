from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI

from .auth import require_token
from . import db
from .congestion_runtime import CongestionRuntime
from .models import CongestionPayload, EventEnvelope, ZoneEvaluationRequest
from .service_config import GATEWAY_URL, HEADERS

app = FastAPI(title="MVTS Congestion Service")
runtime = CongestionRuntime()


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.post("/internal/evaluate", dependencies=[Depends(require_token)])
async def evaluate_zone(payload: ZoneEvaluationRequest) -> dict:
    zone_id = payload.zone_id
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{GATEWAY_URL}/api/state", headers=HEADERS)
        response.raise_for_status()
        positions = [
            v
            for v in response.json()["vehicle_positions"].values()
            if v["zone_id"] == zone_id
        ]

    if not positions:
        runtime.clear_zone(zone_id)
        return {"event": None}

    congestion = runtime.evaluate(positions)
    if not congestion:
        return {"event": None}

    payload_model = CongestionPayload(**congestion)
    event = EventEnvelope(
        event_type="congestion.detected",
        source="congestion-service",
        payload=payload_model.model_dump(mode="json"),
    )
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO congestion_events (id, zone_id, vehicle_count, avg_speed, duration_seconds, severity, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                payload_model.zone_id,
                payload_model.vehicle_count,
                payload_model.avg_speed,
                payload_model.duration_seconds,
                payload_model.severity,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    async with httpx.AsyncClient(timeout=10.0) as client:
        gateway_response = await client.post(
            f"{GATEWAY_URL}/internal/events",
            json=event.model_dump(mode="json"),
            headers=HEADERS,
        )
        gateway_response.raise_for_status()
    return {"event": event.model_dump(mode="json")}
