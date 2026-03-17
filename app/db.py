from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "mvts.db"
DB_PATH = Path(os.getenv("MVTS_DB_PATH", str(DEFAULT_DB_PATH)))


SCHEMA = """
CREATE TABLE IF NOT EXISTS traffic_lights (
    id TEXT PRIMARY KEY,
    zone_id TEXT NOT NULL,
    state TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS material_deliveries (
    id TEXT PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    material_type TEXT NOT NULL,
    quantity_tons REAL NOT NULL,
    delivered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS congestion_events (
    id TEXT PRIMARY KEY,
    zone_id TEXT NOT NULL,
    vehicle_count INTEGER NOT NULL,
    avg_speed REAL NOT NULL,
    duration_seconds INTEGER NOT NULL,
    severity TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traffic_light_audit (
    id TEXT PRIMARY KEY,
    traffic_light_id TEXT NOT NULL,
    previous_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
