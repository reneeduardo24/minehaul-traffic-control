from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from . import db
from .service_config import API_TOKEN

app = FastAPI(title="MVTS Report Service")


async def require_token(x_api_token: str = Header(default="")) -> None:
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


@app.get("/internal/reports/material", dependencies=[Depends(require_token)])
def material_report(period: str = Query("day", enum=["day", "week", "month"])) -> dict:
    now = datetime.now(timezone.utc)
    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(days=7)
    else:  # month
        start_date = now - timedelta(days=30)

    query = "SELECT * FROM material_deliveries WHERE delivered_at >= ? ORDER BY delivered_at DESC"
    results = db.fetch_all(query, (start_date.isoformat(),))

    by_material = Counter(row["material_type"] for row in results)
    total_tons = sum(row["quantity_tons"] for row in results)

    return {
        "period": period,
        "start_date": start_date.isoformat(),
        "delivery_count": len(results),
        "total_tons": round(total_tons, 2),
        "by_material": dict(by_material),
        "deliveries": results,
    }


@app.get("/internal/reports/congestions", dependencies=[Depends(require_token)])
def congestion_history() -> dict:
    results = db.fetch_all("SELECT * FROM congestion_events ORDER BY created_at DESC")
    return {
        "count": len(results),
        "events": results,
    }
