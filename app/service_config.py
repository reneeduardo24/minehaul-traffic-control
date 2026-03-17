from __future__ import annotations

import os

API_TOKEN = os.getenv("MVTS_API_TOKEN", "mvts-demo-token")
GATEWAY_URL = os.getenv("MVTS_GATEWAY_URL", "http://127.0.0.1:8000")
INGEST_URL = os.getenv("MVTS_INGEST_URL", "http://127.0.0.1:8001")
TRAFFIC_LIGHT_URL = os.getenv("MVTS_TRAFFIC_LIGHT_URL", "http://127.0.0.1:8002")
CONGESTION_URL = os.getenv("MVTS_CONGESTION_URL", "http://127.0.0.1:8003")
REPORT_URL = os.getenv("MVTS_REPORT_URL", "http://127.0.0.1:8004")

HEADERS = {"x-api-token": API_TOKEN}
