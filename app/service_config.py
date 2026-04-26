from __future__ import annotations

import os

GATEWAY_URL = os.getenv("MVTS_GATEWAY_URL", "http://127.0.0.1:8000")
TELEMETRY_URL = os.getenv("MVTS_TELEMETRY_URL", "http://127.0.0.1:8001")
TRAFFIC_LIGHT_URL = os.getenv("MVTS_TRAFFIC_LIGHT_URL", "http://127.0.0.1:8002")
TRAFFIC_LIGHT_CONTROLLER_URL = os.getenv(
    "MVTS_TRAFFIC_LIGHT_CONTROLLER_URL", "http://127.0.0.1:8007"
)
CONGESTION_URL = os.getenv("MVTS_CONGESTION_URL", "http://127.0.0.1:8003")
REPORT_URL = os.getenv("MVTS_REPORT_URL", "http://127.0.0.1:8004")
BROKER_URL = os.getenv("MVTS_BROKER_URL", "http://127.0.0.1:8005")
DELIVERY_URL = os.getenv("MVTS_DELIVERY_URL", "http://127.0.0.1:8006")

BROKER_WS_URL = os.getenv(
    "MVTS_BROKER_WS_URL", BROKER_URL.replace("http://", "ws://") + "/internal/events/ws"
)
GATEWAY_WS_URL = os.getenv(
    "MVTS_GATEWAY_WS_URL", GATEWAY_URL.replace("http://", "ws://") + "/ws/events"
)
TELEMETRY_WS_URL = os.getenv(
    "MVTS_TELEMETRY_WS_URL",
    TELEMETRY_URL.replace("http://", "ws://") + "/ingest/telemetry/ws",
)

OPERATOR_TOKEN = os.getenv("MVTS_OPERATOR_TOKEN", "mvts-operator-token")
MANAGER_TOKEN = os.getenv("MVTS_MANAGER_TOKEN", "mvts-manager-token")
SIMULATOR_TOKEN = os.getenv("MVTS_SIMULATOR_TOKEN", "mvts-simulator-token")
GATEWAY_SERVICE_TOKEN = os.getenv(
    "MVTS_GATEWAY_SERVICE_TOKEN", "mvts-gateway-service-token"
)
TELEMETRY_SERVICE_TOKEN = os.getenv(
    "MVTS_TELEMETRY_SERVICE_TOKEN", "mvts-telemetry-service-token"
)
TRAFFIC_LIGHT_SERVICE_TOKEN = os.getenv(
    "MVTS_TRAFFIC_LIGHT_SERVICE_TOKEN", "mvts-traffic-light-service-token"
)
TRAFFIC_LIGHT_CONTROLLER_SERVICE_TOKEN = os.getenv(
    "MVTS_TRAFFIC_LIGHT_CONTROLLER_SERVICE_TOKEN",
    "mvts-traffic-light-controller-service-token",
)
CONGESTION_SERVICE_TOKEN = os.getenv(
    "MVTS_CONGESTION_SERVICE_TOKEN", "mvts-congestion-service-token"
)
DELIVERY_SERVICE_TOKEN = os.getenv(
    "MVTS_DELIVERY_SERVICE_TOKEN", "mvts-delivery-service-token"
)
REPORT_SERVICE_TOKEN = os.getenv(
    "MVTS_REPORT_SERVICE_TOKEN", "mvts-report-service-token"
)
REPORT_CONSUMER_SERVICE_TOKEN = os.getenv(
    "MVTS_REPORT_CONSUMER_SERVICE_TOKEN", "mvts-report-consumer-service-token"
)
BROKER_SERVICE_TOKEN = os.getenv("MVTS_BROKER_SERVICE_TOKEN", "mvts-broker-service-token")


def bearer_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
