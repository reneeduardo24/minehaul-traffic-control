from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException

from .auth import require_token
from . import db
from .models import (
    EventEnvelope,
    TrafficLightChangedPayload,
    TrafficLightCommand,
    TrafficLightState,
)
from .service_config import API_TOKEN, GATEWAY_URL, HEADERS
from .topology import TRAFFIC_LIGHTS, build_default_traffic_lights

app = FastAPI(title="MVTS Traffic Light Service")
traffic_lights: dict[str, dict] = {}


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    defaults = build_default_traffic_lights()
    with db.connect() as conn:
        for light_id, light in defaults.items():
            conn.execute(
                """
                INSERT INTO traffic_lights (id, zone_id, state, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET zone_id = excluded.zone_id
                """,
                (
                    light_id,
                    light["zone_id"],
                    light["state"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        rows = conn.execute("SELECT id, zone_id, state FROM traffic_lights ORDER BY id").fetchall()
        conn.commit()

    metadata = {light["id"]: light for light in TRAFFIC_LIGHTS}
    traffic_lights.clear()
    for row in rows:
        light_meta = metadata[row["id"]]
        traffic_lights[row["id"]] = {
            "zone_id": row["zone_id"],
            "state": TrafficLightState(row["state"]),
            "x": light_meta["x"],
            "y": light_meta["y"],
            "label": light_meta["label"],
            "label_dx": light_meta["label_dx"],
            "label_dy": light_meta["label_dy"],
            "label_anchor": light_meta["label_anchor"],
        }


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
