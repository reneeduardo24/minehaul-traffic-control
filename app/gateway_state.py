from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass
class GatewayConnectionManager:
    connections: list[WebSocket] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def register(self, websocket: WebSocket, bootstrap_payload: dict[str, Any]) -> None:
        await websocket.accept()
        async with self.lock:
            self.connections.append(websocket)
        await websocket.send_json(
            {
                "event_type": "state.bootstrap",
                "source": "gateway",
                "payload": bootstrap_payload,
            }
        )

    async def unregister(self, websocket: WebSocket) -> None:
        async with self.lock:
            if websocket in self.connections:
                self.connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        encoded = json.dumps(message, default=str)
        stale: list[WebSocket] = []
        async with self.lock:
            targets = list(self.connections)
        for connection in targets:
            try:
                await connection.send_text(encoded)
            except Exception:
                stale.append(connection)
        for connection in stale:
            await self.unregister(connection)
