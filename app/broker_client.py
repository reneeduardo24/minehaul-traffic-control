from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

import httpx
import websockets

from .models import BrokerSubscriptionRequest, EventEnvelope, EventType
from .service_config import BROKER_URL, BROKER_WS_URL, bearer_headers

logger = logging.getLogger(__name__)


async def publish_event(event: EventEnvelope, token: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{BROKER_URL}/internal/events",
            json=event.model_dump(mode="json"),
            headers=bearer_headers(token),
        )
        response.raise_for_status()


async def run_subscription_loop(
    *,
    subscriber_name: str,
    token: str,
    event_types: list[EventType],
    handler: Callable[[EventEnvelope], Awaitable[None]],
) -> None:
    subscription = BrokerSubscriptionRequest(subscribe=event_types)
    retry_delay = 1.0
    while True:
        try:
            async with websockets.connect(
                BROKER_WS_URL,
                additional_headers=bearer_headers(token),
                ping_interval=20,
                ping_timeout=20,
            ) as websocket:
                await websocket.send(subscription.model_dump_json())
                await websocket.recv()
                retry_delay = 1.0
                while True:
                    raw = await websocket.recv()
                    event = EventEnvelope.model_validate(json.loads(raw))
                    await handler(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "%s subscription disconnected: %s. Retrying in %.1fs",
                subscriber_name,
                exc,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 10.0)
