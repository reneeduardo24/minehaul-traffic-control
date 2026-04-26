from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect

from .auth import principal_from_websocket, require_any_role
from .models import BrokerSubscriptionRequest, EventEnvelope

app = FastAPI(title="MVTS Event Broker")


@dataclass
class BrokerSubscriber:
    websocket: WebSocket
    event_types: set[str]


subscribers: list[BrokerSubscriber] = []
subscribers_lock = asyncio.Lock()


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Event Broker", "status": "ok"}


@app.post("/internal/events", dependencies=[Depends(require_any_role("service"))])
async def publish_internal_event(event: EventEnvelope) -> dict:
    await broadcast_event(event)
    return {"accepted": True, "event_id": event.event_id}


@app.websocket("/internal/events/ws")
async def subscribe_to_events(websocket: WebSocket) -> None:
    principal = principal_from_websocket(websocket)
    if principal is None or not principal.has_any_role("service", "simulator"):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        request = BrokerSubscriptionRequest.model_validate(json.loads(raw))
        subscriber = BrokerSubscriber(
            websocket=websocket,
            event_types={event_type.value for event_type in request.subscribe},
        )
        async with subscribers_lock:
            subscribers.append(subscriber)
        await websocket.send_json(
            {
                "subscription": "accepted",
                "event_types": sorted(subscriber.event_types),
                "principal": principal.name,
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        async with subscribers_lock:
            subscribers[:] = [item for item in subscribers if item.websocket is not websocket]


async def broadcast_event(event: EventEnvelope) -> None:
    message = event.model_dump_json()
    stale: list[BrokerSubscriber] = []
    async with subscribers_lock:
        targets = list(subscribers)
    for subscriber in targets:
        if event.event_type.value not in subscriber.event_types:
            continue
        try:
            await subscriber.websocket.send_text(message)
        except Exception:
            stale.append(subscriber)
    if stale:
        async with subscribers_lock:
            subscribers[:] = [item for item in subscribers if item not in stale]
