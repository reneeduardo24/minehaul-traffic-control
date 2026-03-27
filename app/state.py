from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

from . import db
from .models import (
    CongestionPayload,
    EventEnvelope,
    MaterialDelivery,
    TrafficLightChangedPayload,
    TrafficLightCommand,
    TrafficLightState,
    VehiclePositionPayload,
)


@dataclass
class AppState:
    traffic_lights: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "TL-01": {"zone_id": "Z1", "state": TrafficLightState.GREEN},
            "TL-02": {"zone_id": "Z2", "state": TrafficLightState.RED},
        }
    )
    vehicle_positions: dict[str, dict[str, Any]] = field(default_factory=dict)
    zone_slow_since: dict[str, datetime] = field(default_factory=dict)
    congestion_active: set[str] = field(default_factory=set)
    connections: list[WebSocket] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def broadcast(self, event: EventEnvelope) -> None:
        message = json.dumps(event.model_dump(mode="json"), default=str)
        stale: list[WebSocket] = []
        for connection in self.connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            if connection in self.connections:
                self.connections.remove(connection)

    async def register_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append(websocket)
        await websocket.send_json(
            {
                "traffic_lights": {
                    key: {**value, "state": value["state"].value}
                    for key, value in self.traffic_lights.items()
                },
                "vehicle_positions": self.vehicle_positions,
            }
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "traffic_lights": {
                key: {**value, "state": value["state"].value}
                for key, value in self.traffic_lights.items()
            },
            "vehicle_positions": self.vehicle_positions,
        }

    def seed_traffic_lights(self) -> None:
        with db.connect() as conn:
            for light_id, light in self.traffic_lights.items():
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

    async def handle_vehicle_position(
        self, payload: VehiclePositionPayload
    ) -> EventEnvelope | None:
        self.vehicle_positions[payload.vehicle_id] = payload.model_dump(mode="json")
        event = EventEnvelope(
            event_type="vehicle.position.updated",
            source="vehicle-simulator",
            payload=payload.model_dump(mode="json"),
        )
        await self.broadcast(event)
        return await self.evaluate_congestion(payload.zone_id)

    async def handle_delivery(self, delivery: MaterialDelivery) -> None:
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
        await self.broadcast(event)

    async def handle_traffic_light_command(
        self, command: TrafficLightCommand
    ) -> EventEnvelope:
        light = self.traffic_lights[command.traffic_light_id]
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
        await self.broadcast(event)
        return event

    async def evaluate_congestion(self, zone_id: str) -> EventEnvelope | None:
        vehicles = [
            v for v in self.vehicle_positions.values() if v["zone_id"] == zone_id
        ]
        if not vehicles:
            self.zone_slow_since.pop(zone_id, None)
            self.congestion_active.discard(zone_id)
            return None

        avg_speed = sum(v["speed"] for v in vehicles) / len(vehicles)
        now = datetime.now(timezone.utc)
        if len(vehicles) >= 3 and avg_speed <= 1.0:
            self.zone_slow_since.setdefault(zone_id, now)
            duration = int((now - self.zone_slow_since[zone_id]).total_seconds())
            if duration >= 5 and zone_id not in self.congestion_active:
                self.congestion_active.add(zone_id)
                severity = "HIGH" if len(vehicles) >= 5 else "MEDIUM"
                payload = CongestionPayload(
                    zone_id=zone_id,
                    vehicle_count=len(vehicles),
                    avg_speed=round(avg_speed, 2),
                    duration_seconds=duration,
                    severity=severity,
                )
                with db.connect() as conn:
                    conn.execute(
                        "INSERT INTO congestion_events (id, zone_id, vehicle_count, avg_speed, duration_seconds, severity, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid4()),
                            payload.zone_id,
                            payload.vehicle_count,
                            payload.avg_speed,
                            payload.duration_seconds,
                            payload.severity,
                            now.isoformat(),
                        ),
                    )
                    conn.commit()
                event = EventEnvelope(
                    event_type="congestion.detected",
                    source="congestion-service",
                    payload=payload.model_dump(mode="json"),
                )
                await self.broadcast(event)
                return event
        else:
            self.zone_slow_since.pop(zone_id, None)
            self.congestion_active.discard(zone_id)
        return None
