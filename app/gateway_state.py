from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass
class GatewayState:
    traffic_lights: dict[str, dict[str, Any]] = field(default_factory=dict)
    vehicle_positions: dict[str, dict[str, Any]] = field(default_factory=dict)
    connections: list[WebSocket] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def register_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append(websocket)
        await websocket.send_json(self.snapshot())

    def snapshot(self) -> dict[str, Any]:
        return {
            "traffic_lights": self.traffic_lights,
            "vehicle_positions": self.vehicle_positions,
        }

    async def apply_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("event_type")
        payload = event.get("payload", {})
        if event_type == "vehicle.position.updated":
            self.vehicle_positions[payload["vehicle_id"]] = payload
        elif event_type == "traffic_light.changed":
            self.traffic_lights[payload["traffic_light_id"]] = {
                "zone_id": payload["zone_id"],
                "state": payload["new_state"],
            }
        await self.broadcast(event)

    async def set_traffic_lights(self, lights: dict[str, dict[str, Any]]) -> None:
        self.traffic_lights = lights

    async def broadcast(self, event: dict[str, Any]) -> None:
        message = json.dumps(event, default=str)
        stale: list[WebSocket] = []
        for connection in self.connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            if connection in self.connections:
                self.connections.remove(connection)
