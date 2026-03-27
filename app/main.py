from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect

from .service_config import API_TOKEN, HEADERS, REPORT_URL
from .services_gateway import app as gateway_app, state

app = gateway_app


async def require_token(x_api_token: str = Header(default="")) -> None:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


@app.get("/api/reports/summary", dependencies=[Depends(require_token)])
async def summary_report() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{REPORT_URL}/internal/reports/summary", headers=HEADERS)
        response.raise_for_status()
        return response.json()
