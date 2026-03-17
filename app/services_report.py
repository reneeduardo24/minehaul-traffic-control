from __future__ import annotations

from collections import Counter

from fastapi import Depends, FastAPI, Header, HTTPException

from . import db
from .service_config import API_TOKEN

app = FastAPI(title="MVTS Report Service")


def require_token(x_api_token: str = Header(default="")) -> None:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.get("/internal/reports/summary", dependencies=[Depends(require_token)])
def summary_report() -> dict:
    deliveries = db.fetch_all("SELECT * FROM material_deliveries ORDER BY delivered_at DESC")
    congestions = db.fetch_all("SELECT * FROM congestion_events ORDER BY created_at DESC")
    by_material = Counter(row["material_type"] for row in deliveries)
    return {
        "delivery_count": len(deliveries),
        "congestion_count": len(congestions),
        "tons_total": round(sum(row["quantity_tons"] for row in deliveries), 2),
        "deliveries_by_material": dict(by_material),
        "latest_congestion": congestions[0] if congestions else None,
    }
