from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException

from . import db
from .models import (
    EventEnvelope,
    TrafficLightChangedPayload,
    TrafficLightCommand,
    TrafficLightState,
)
from .service_config import API_TOKEN, GATEWAY_URL, HEADERS

app = FastAPI(title="MVTS Traffic Light Service")
traffic_lights = {
    "TL-01": {"zone_id": "Z1", "state": TrafficLightState.GREEN},
    "TL-02": {"zone_id": "Z2", "state": TrafficLightState.RED},
}


async def require_token(x_api_token: str = Header(default="")) -> None:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    with db.connect() as conn:
        for light_id, light in traffic_lights.items():
            conn.execute(
                """
                INSERT INTO traffic_lights (id, zone_id, state, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET zone_id=excluded.zone_id, state=excluded.state, updated_at=excluded.updated_at
                """,
                (
                    light_id,
                    light["zone_id"],
                    light["state"].value,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        conn.commit()


@app.get("/internal/traffic-lights", dependencies=[Depends(require_token)])
def get_traffic_lights() -> dict:
    return {
        "traffic_lights": {
            key: {**value, "state": value["state"].value}
            for key, value in traffic_lights.items()
        }
    }


@app.post("/internal/traffic-lights/change", dependencies=[Depends(require_token)])
async def change_traffic_light(command: TrafficLightCommand) -> dict:
    if command.traffic_light_id not in traffic_lights:
        raise HTTPException(status_code=404, detail="traffic light not found")

    light = traffic_lights[command.traffic_light_id]
    previous_state = light["state"]
    light["state"] = command.new_state
    changed_at = datetime.now(timezone.utc).isoformat()

    with db.connect() as conn:
        conn.execute(
            "UPDATE traffic_lights SET state = ?, updated_at = ? WHERE id = ?",
            (command.new_state.value, changed_at, command.traffic_light_id),
        )
        conn.execute(
            "INSERT INTO traffic_light_audit (id, traffic_light_id, previous_state, new_state, changed_by, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                command.traffic_light_id,
                previous_state.value,
                command.new_state.value,
                command.changed_by,
                changed_at,
            ),
        )
        conn.commit()

    payload = TrafficLightChangedPayload(
        traffic_light_id=command.traffic_light_id,
        zone_id=light["zone_id"],
        previous_state=previous_state,
        new_state=command.new_state,
        changed_by=command.changed_by,
    )
    event = EventEnvelope(
        event_type="traffic_light.changed",
        source="traffic-light-service",
        payload=payload.model_dump(mode="json"),
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{GATEWAY_URL}/internal/events",
            json=event.model_dump(mode="json"),
            headers=HEADERS,
        )
        response.raise_for_status()
    return {"accepted": True, "event": event.model_dump(mode="json")}
