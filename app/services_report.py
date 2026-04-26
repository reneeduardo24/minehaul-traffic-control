from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Query

from .auth import require_any_role
from .persistence import connect, fetch_all, init_service_db

app = FastAPI(title="MVTS Report Service")


@app.on_event("startup")
def startup() -> None:
    init_service_db("report")


@app.get("/")
def root() -> dict:
    return {"name": "MVTS Report Service", "status": "ok"}


@app.get("/internal/reports/summary", dependencies=[Depends(require_any_role("gateway", "service"))])
def summary_report() -> dict:
    deliveries = fetch_all(
        "report", "SELECT * FROM material_deliveries ORDER BY delivered_at DESC"
    )
    congestion_events = fetch_all(
        "report",
        "SELECT * FROM congestion_events WHERE event_kind = 'DETECTED' ORDER BY occurred_at DESC",
    )
    by_material = Counter(row["material_type"] for row in deliveries)
    return {
        "delivery_count": len(deliveries),
        "congestion_count": len(congestion_events),
        "tons_total": round(sum(row["quantity_tons"] for row in deliveries), 2),
        "deliveries_by_material": dict(by_material),
        "latest_congestion": congestion_events[0] if congestion_events else None,
    }


@app.get("/internal/reports/material", dependencies=[Depends(require_any_role("gateway", "service"))])
def material_report(period: str = Query("day", enum=["day", "week", "month"])) -> dict:
    now = datetime.now(timezone.utc)
    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(days=7)
    else:
        start_date = now - timedelta(days=30)

    rows = fetch_all(
        "report",
        "SELECT * FROM material_deliveries WHERE delivered_at >= ? ORDER BY delivered_at DESC",
        (start_date.isoformat(),),
    )
    by_material = Counter(row["material_type"] for row in rows)
    return {
        "period": period,
        "start_date": start_date.isoformat(),
        "delivery_count": len(rows),
        "total_tons": round(sum(row["quantity_tons"] for row in rows), 2),
        "by_material": dict(by_material),
        "deliveries": rows,
    }


@app.get("/internal/reports/congestions", dependencies=[Depends(require_any_role("gateway", "service"))])
def congestion_history() -> dict:
    rows = fetch_all(
        "report",
        "SELECT * FROM congestion_events ORDER BY occurred_at DESC",
    )
    return {"count": len(rows), "events": rows}
