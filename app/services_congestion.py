from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI

from .auth import require_any_role
from .broker_client import publish_event, run_subscription_loop
from .congestion_runtime import CongestionRuntime
from .models import CongestionPayload, EventEnvelope, EventType, VehiclePositionPayload
from .persistence import connect, fetch_all, init_service_db
from .service_config import CONGESTION_SERVICE_TOKEN, TELEMETRY_URL, bearer_headers

app = FastAPI(title="MVTS Congestion Service")
runtime = CongestionRuntime()


@app.on_event("startup")
async def startup() -> None:
    init_service_db("congestion")
    active = fetch_all(
        "congestion",
        "SELECT zone_id, vehicle_count, avg_speed, duration_seconds, severity, updated_at FROM active_congestions",
    )
    runtime.load_active_congestions(active)
    await bootstrap_positions()
    app.state.subscription_task = asyncio.create_task(subscribe_to_position_events())


@app.on_event("shutdown")
async def shutdown() -> None:
    task = getattr(app.state, "subscription_task", None)
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Congestion Service", "status": "ok"}


@app.get("/internal/congestion/active", dependencies=[Depends(require_any_role("gateway", "service"))])
def active_congestions() -> dict:
    rows = fetch_all(
        "congestion",
        "SELECT zone_id, vehicle_count, avg_speed, duration_seconds, severity, updated_at FROM active_congestions ORDER BY zone_id",
    )
    return {"active_congestions": {row["zone_id"]: row for row in rows}}


@app.get("/internal/congestion/history", dependencies=[Depends(require_any_role("gateway", "report", "service"))])
def congestion_history() -> dict:
    rows = fetch_all(
        "congestion",
        "SELECT source_event_id, zone_id, event_kind, vehicle_count, avg_speed, duration_seconds, severity, occurred_at FROM congestion_events ORDER BY occurred_at DESC",
    )
    return {"events": rows}


async def bootstrap_positions() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{TELEMETRY_URL}/internal/telemetry/positions",
            headers=bearer_headers(CONGESTION_SERVICE_TOKEN),
        )
        response.raise_for_status()
        positions = list(response.json()["vehicle_positions"].values())
        runtime.load_positions(positions)


async def subscribe_to_position_events() -> None:
    await run_subscription_loop(
        subscriber_name="congestion-service",
        token=CONGESTION_SERVICE_TOKEN,
        event_types=[EventType.VEHICLE_POSITION_UPDATED],
        handler=handle_position_event,
    )


async def handle_position_event(event: EventEnvelope) -> None:
    with connect("congestion") as conn:
        inserted = conn.execute(
            "INSERT OR IGNORE INTO processed_events (event_id, processed_at) VALUES (?, ?)",
            (event.event_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        if inserted.rowcount == 0:
            return

    payload = VehiclePositionPayload.model_validate(event.payload)
    domain_events = runtime.apply_position(payload.model_dump(mode="json"))
    for event_type, congestion_payload in domain_events:
        await persist_and_publish_congestion(event_type, congestion_payload)


async def persist_and_publish_congestion(
    event_type: EventType, payload: CongestionPayload
) -> None:
    event = EventEnvelope(
        event_type=event_type,
        source="congestion-service",
        payload=payload.model_dump(mode="json"),
    )

    with connect("congestion") as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO congestion_events (source_event_id, zone_id, event_kind, vehicle_count, avg_speed, duration_seconds, severity, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                payload.zone_id,
                "DETECTED" if event_type == EventType.CONGESTION_DETECTED else "CLEARED",
                payload.vehicle_count,
                payload.avg_speed,
                payload.duration_seconds,
                payload.severity.value,
                payload.occurred_at.isoformat(),
            ),
        )
        if event_type == EventType.CONGESTION_DETECTED:
            conn.execute(
                """
                INSERT INTO active_congestions (zone_id, vehicle_count, avg_speed, duration_seconds, severity, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(zone_id) DO UPDATE SET
                    vehicle_count = excluded.vehicle_count,
                    avg_speed = excluded.avg_speed,
                    duration_seconds = excluded.duration_seconds,
                    severity = excluded.severity,
                    updated_at = excluded.updated_at
                """,
                (
                    payload.zone_id,
                    payload.vehicle_count,
                    payload.avg_speed,
                    payload.duration_seconds,
                    payload.severity.value,
                    payload.occurred_at.isoformat(),
                ),
            )
        else:
            conn.execute("DELETE FROM active_congestions WHERE zone_id = ?", (payload.zone_id,))
        conn.commit()

    await publish_event(event, CONGESTION_SERVICE_TOKEN)
