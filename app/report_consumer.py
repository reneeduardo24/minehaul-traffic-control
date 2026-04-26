from __future__ import annotations

import asyncio

import httpx

from .broker_client import run_subscription_loop
from .models import EventEnvelope, EventType, MaterialDelivery
from .persistence import connect, init_service_db
from .service_config import (
    CONGESTION_URL,
    DELIVERY_URL,
    REPORT_CONSUMER_SERVICE_TOKEN,
    bearer_headers,
)


async def bootstrap_from_owners() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            delivery_response = await client.get(
                f"{DELIVERY_URL}/internal/deliveries",
                headers=bearer_headers(REPORT_CONSUMER_SERVICE_TOKEN),
            )
            delivery_response.raise_for_status()
            for delivery in delivery_response.json()["deliveries"]:
                persist_delivery_snapshot(delivery)
        except httpx.HTTPError:
            pass

        try:
            congestion_response = await client.get(
                f"{CONGESTION_URL}/internal/congestion/history",
                headers=bearer_headers(REPORT_CONSUMER_SERVICE_TOKEN),
            )
            congestion_response.raise_for_status()
            for event in congestion_response.json()["events"]:
                persist_congestion_snapshot(event)
        except httpx.HTTPError:
            pass


def persist_delivery_snapshot(delivery: dict) -> None:
    with connect("report") as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO material_deliveries (id, source_event_id, vehicle_id, origin, destination, material_type, quantity_tons, delivered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                delivery["id"],
                delivery.get("source_event_id") or delivery["id"],
                delivery["vehicle_id"],
                delivery["origin"],
                delivery["destination"],
                delivery["material_type"],
                delivery["quantity_tons"],
                delivery["delivered_at"],
            ),
        )
        conn.commit()


def persist_congestion_snapshot(event: dict) -> None:
    with connect("report") as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO congestion_events (source_event_id, zone_id, event_kind, vehicle_count, avg_speed, duration_seconds, severity, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["source_event_id"],
                event["zone_id"],
                event["event_kind"],
                event["vehicle_count"],
                event["avg_speed"],
                event["duration_seconds"],
                event["severity"],
                event["occurred_at"],
            ),
        )
        conn.commit()


async def handle_domain_event(event: EventEnvelope) -> None:
    with connect("report") as conn:
        if event.event_type == EventType.DELIVERY_CREATED:
            delivery = MaterialDelivery.model_validate(event.payload)
            conn.execute(
                """
                INSERT OR IGNORE INTO material_deliveries (id, source_event_id, vehicle_id, origin, destination, material_type, quantity_tons, delivered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery.delivery_id,
                    event.event_id,
                    delivery.vehicle_id,
                    delivery.origin,
                    delivery.destination,
                    delivery.material_type,
                    delivery.quantity_tons,
                    delivery.timestamp.isoformat(),
                ),
            )
        else:
            payload = event.payload
            conn.execute(
                """
                INSERT OR IGNORE INTO congestion_events (source_event_id, zone_id, event_kind, vehicle_count, avg_speed, duration_seconds, severity, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    payload["zone_id"],
                    "DETECTED" if event.event_type == EventType.CONGESTION_DETECTED else "CLEARED",
                    payload["vehicle_count"],
                    payload["avg_speed"],
                    payload["duration_seconds"],
                    payload["severity"],
                    payload["occurred_at"],
                ),
            )
        conn.commit()


async def main() -> None:
    init_service_db("report")
    await bootstrap_from_owners()
    print("[report-consumer] subscribed to report events", flush=True)
    await run_subscription_loop(
        subscriber_name="report-consumer",
        token=REPORT_CONSUMER_SERVICE_TOKEN,
        event_types=[
            EventType.DELIVERY_CREATED,
            EventType.CONGESTION_DETECTED,
            EventType.CONGESTION_CLEARED,
        ],
        handler=handle_domain_event,
    )


if __name__ == "__main__":
    asyncio.run(main())
