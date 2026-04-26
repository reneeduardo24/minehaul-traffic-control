from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

BASE_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

SERVICE_DB_ENV = {
    "telemetry": "MVTS_TELEMETRY_DB_PATH",
    "traffic_light": "MVTS_TRAFFIC_LIGHT_DB_PATH",
    "congestion": "MVTS_CONGESTION_DB_PATH",
    "delivery": "MVTS_DELIVERY_DB_PATH",
    "report": "MVTS_REPORT_DB_PATH",
}

SERVICE_DB_DEFAULTS = {
    "telemetry": "telemetry.db",
    "traffic_light": "traffic_light.db",
    "congestion": "congestion.db",
    "delivery": "delivery.db",
    "report": "report.db",
}

SERVICE_SCHEMAS = {
    "telemetry": """
    CREATE TABLE IF NOT EXISTS latest_vehicle_positions (
        vehicle_id TEXT PRIMARY KEY,
        zone_id TEXT NOT NULL,
        x REAL NOT NULL,
        y REAL NOT NULL,
        speed REAL NOT NULL,
        destination TEXT NOT NULL,
        material_type TEXT,
        observed_at TEXT NOT NULL
    );
    """,
    "traffic_light": """
    CREATE TABLE IF NOT EXISTS traffic_lights (
        id TEXT PRIMARY KEY,
        zone_id TEXT NOT NULL,
        state TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS traffic_light_audit (
        id TEXT PRIMARY KEY,
        source_event_id TEXT UNIQUE NOT NULL,
        traffic_light_id TEXT NOT NULL,
        previous_state TEXT NOT NULL,
        new_state TEXT NOT NULL,
        changed_by TEXT NOT NULL,
        changed_at TEXT NOT NULL
    );
    """,
    "congestion": """
    CREATE TABLE IF NOT EXISTS congestion_events (
        source_event_id TEXT PRIMARY KEY,
        zone_id TEXT NOT NULL,
        event_kind TEXT NOT NULL,
        vehicle_count INTEGER NOT NULL,
        avg_speed REAL NOT NULL,
        duration_seconds INTEGER NOT NULL,
        severity TEXT NOT NULL,
        occurred_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS active_congestions (
        zone_id TEXT PRIMARY KEY,
        vehicle_count INTEGER NOT NULL,
        avg_speed REAL NOT NULL,
        duration_seconds INTEGER NOT NULL,
        severity TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS processed_events (
        event_id TEXT PRIMARY KEY,
        processed_at TEXT NOT NULL
    );
    """,
    "delivery": """
    CREATE TABLE IF NOT EXISTS material_deliveries (
        id TEXT PRIMARY KEY,
        source_event_id TEXT UNIQUE,
        vehicle_id TEXT NOT NULL,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        material_type TEXT NOT NULL,
        quantity_tons REAL NOT NULL,
        delivered_at TEXT NOT NULL
    );
    """,
    "report": """
    CREATE TABLE IF NOT EXISTS material_deliveries (
        id TEXT PRIMARY KEY,
        source_event_id TEXT UNIQUE NOT NULL,
        vehicle_id TEXT NOT NULL,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        material_type TEXT NOT NULL,
        quantity_tons REAL NOT NULL,
        delivered_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS congestion_events (
        source_event_id TEXT PRIMARY KEY,
        zone_id TEXT NOT NULL,
        event_kind TEXT NOT NULL,
        vehicle_count INTEGER NOT NULL,
        avg_speed REAL NOT NULL,
        duration_seconds INTEGER NOT NULL,
        severity TEXT NOT NULL,
        occurred_at TEXT NOT NULL
    );
    """,
}


def get_db_path(service_name: str) -> Path:
    env_name = SERVICE_DB_ENV[service_name]
    configured = os.getenv(env_name)
    if configured:
        return Path(configured)
    return BASE_DATA_DIR / SERVICE_DB_DEFAULTS[service_name]


def connect(service_name: str) -> sqlite3.Connection:
    path = get_db_path(service_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_service_db(service_name: str) -> None:
    schema = SERVICE_SCHEMAS[service_name]
    with connect(service_name) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(schema)
        conn.commit()


def fetch_all(service_name: str, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect(service_name) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def fetch_one(service_name: str, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with connect(service_name) as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row is not None else None
