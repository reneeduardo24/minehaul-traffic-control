from __future__ import annotations

import httpx
from fastapi import Depends

from .auth import require_token
from .service_config import HEADERS, REPORT_URL
from .services_gateway import app as gateway_app

app = gateway_app


@app.get("/api/reports/summary", dependencies=[Depends(require_token)])
async def summary_report() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{REPORT_URL}/internal/reports/summary", headers=HEADERS
        )
        response.raise_for_status()
        return response.json()
