from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, HTTPException

from .auth import require_any_role
from .models import TrafficLightCommand
from .service_config import (
    TRAFFIC_LIGHT_CONTROLLER_SERVICE_TOKEN,
    TRAFFIC_LIGHT_URL,
    bearer_headers,
)
from .topology import TRAFFIC_LIGHTS

app = FastAPI(title="MVTS Traffic-Light Controller")
valid_traffic_light_ids = {item["id"] for item in TRAFFIC_LIGHTS}


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Traffic-Light Controller", "status": "ok"}


@app.post("/internal/traffic-lights/change", dependencies=[Depends(require_any_role("gateway"))])
async def change_traffic_light(command: TrafficLightCommand) -> dict:
    if command.traffic_light_id not in valid_traffic_light_ids:
        raise HTTPException(status_code=404, detail="traffic light not found")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{TRAFFIC_LIGHT_URL}/internal/traffic-lights/apply-command",
            json=command.model_dump(mode="json"),
            headers=bearer_headers(TRAFFIC_LIGHT_CONTROLLER_SERVICE_TOKEN),
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="traffic light not found")
        response.raise_for_status()
        result = response.json()

    return {**result, "routed_by": "traffic-light-controller"}
