from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException

from .auth import require_any_role
from .broker_client import publish_event
from .models import EventEnvelope, EventType, TrafficLightChangedPayload, TrafficLightCommand, TrafficLightState
from .persistence import connect, fetch_all, init_service_db
from .service_config import TRAFFIC_LIGHT_SERVICE_TOKEN
from .topology import TRAFFIC_LIGHTS, build_default_traffic_lights

app = FastAPI(title="MVTS Traffic-Light Device Service")
traffic_light_metadata = {item["id"]: item for item in TRAFFIC_LIGHTS}


@app.on_event("startup")
def startup() -> None:
    init_service_db("traffic_light")
    defaults = build_default_traffic_lights()
    with connect("traffic_light") as conn:
        for light_id, light in defaults.items():
            conn.execute(
                """
                INSERT INTO traffic_lights (id, zone_id, state, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    light_id,
                    light["zone_id"],
                    light["state"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        conn.commit()


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Traffic-Light Device Service", "status": "ok"}


@app.get("/internal/traffic-lights", dependencies=[Depends(require_any_role("gateway", "simulator", "service"))])
def get_traffic_lights() -> dict:
    rows = fetch_all(
        "traffic_light",
        "SELECT id, zone_id, state, updated_at FROM traffic_lights ORDER BY id",
    )
    payload: dict[str, dict] = {}
    for row in rows:
        meta = traffic_light_metadata[row["id"]]
        payload[row["id"]] = {
            "id": row["id"],
            "zone_id": row["zone_id"],
            "state": row["state"],
            "updated_at": row["updated_at"],
            "x": meta["x"],
            "y": meta["y"],
            "label": meta["label"],
            "label_dx": meta["label_dx"],
            "label_dy": meta["label_dy"],
            "label_anchor": meta["label_anchor"],
        }
    return {"traffic_lights": payload}


@app.post(
    "/internal/traffic-lights/apply-command",
    dependencies=[Depends(require_any_role("traffic_light_controller"))],
)
async def apply_traffic_light_command(command: TrafficLightCommand) -> dict:
    rows = fetch_all(
        "traffic_light",
        "SELECT id, zone_id, state FROM traffic_lights WHERE id = ?",
        (command.traffic_light_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="traffic light not found")

    row = rows[0]
    previous_state = TrafficLightState(row["state"])
    changed_at = datetime.now(timezone.utc)

    with connect("traffic_light") as conn:
        conn.execute(
            "UPDATE traffic_lights SET state = ?, updated_at = ? WHERE id = ?",
            (command.new_state.value, changed_at.isoformat(), command.traffic_light_id),
        )
        conn.commit()

    payload = TrafficLightChangedPayload(
        traffic_light_id=command.traffic_light_id,
        zone_id=row["zone_id"],
        previous_state=previous_state,
        new_state=command.new_state,
        changed_by=command.changed_by,
        changed_at=changed_at,
    )
    event = EventEnvelope(
        event_type=EventType.TRAFFIC_LIGHT_CHANGED,
        source="traffic-light-device",
        payload=payload.model_dump(mode="json"),
    )

    with connect("traffic_light") as conn:
        conn.execute(
            """
            INSERT INTO traffic_light_audit (id, source_event_id, traffic_light_id, previous_state, new_state, changed_by, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                event.event_id,
                command.traffic_light_id,
                previous_state.value,
                command.new_state.value,
                command.changed_by,
                changed_at.isoformat(),
            ),
        )
        conn.commit()

    await publish_event(event, TRAFFIC_LIGHT_SERVICE_TOKEN)
    return {"accepted": True, "event": event.model_dump(mode="json")}
