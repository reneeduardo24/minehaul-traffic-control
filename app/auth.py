from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, WebSocket

from .service_config import (
    BROKER_SERVICE_TOKEN,
    CONGESTION_SERVICE_TOKEN,
    DELIVERY_SERVICE_TOKEN,
    GATEWAY_SERVICE_TOKEN,
    MANAGER_TOKEN,
    OPERATOR_TOKEN,
    REPORT_CONSUMER_SERVICE_TOKEN,
    REPORT_SERVICE_TOKEN,
    SIMULATOR_TOKEN,
    TELEMETRY_SERVICE_TOKEN,
    TRAFFIC_LIGHT_CONTROLLER_SERVICE_TOKEN,
    TRAFFIC_LIGHT_SERVICE_TOKEN,
)


@dataclass(frozen=True)
class Principal:
    name: str
    roles: frozenset[str]

    def has_any_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


TOKEN_PRINCIPALS = {
    OPERATOR_TOKEN: Principal("operator", frozenset({"operator"})),
    MANAGER_TOKEN: Principal("manager", frozenset({"manager"})),
    SIMULATOR_TOKEN: Principal("simulator", frozenset({"simulator"})),
    GATEWAY_SERVICE_TOKEN: Principal("gateway-service", frozenset({"service", "gateway"})),
    TELEMETRY_SERVICE_TOKEN: Principal(
        "telemetry-service", frozenset({"service", "telemetry"})
    ),
    TRAFFIC_LIGHT_SERVICE_TOKEN: Principal(
        "traffic-light-service", frozenset({"service", "traffic_light"})
    ),
    TRAFFIC_LIGHT_CONTROLLER_SERVICE_TOKEN: Principal(
        "traffic-light-controller-service",
        frozenset({"service", "traffic_light_controller"}),
    ),
    CONGESTION_SERVICE_TOKEN: Principal(
        "congestion-service", frozenset({"service", "congestion"})
    ),
    DELIVERY_SERVICE_TOKEN: Principal(
        "delivery-service", frozenset({"service", "delivery"})
    ),
    REPORT_SERVICE_TOKEN: Principal(
        "report-service", frozenset({"service", "report"})
    ),
    REPORT_CONSUMER_SERVICE_TOKEN: Principal(
        "report-consumer", frozenset({"service", "report_consumer"})
    ),
    BROKER_SERVICE_TOKEN: Principal("broker-service", frozenset({"service", "broker"})),
}


def extract_bearer_token(authorization: str | None) -> str:
    if authorization:
        prefix = "Bearer "
        if authorization.startswith(prefix):
            return authorization[len(prefix) :].strip()
        return authorization.strip()
    return ""


def principal_for_token(token: str) -> Principal | None:
    return TOKEN_PRINCIPALS.get(token)


async def get_principal(
    authorization: str | None = Header(default=None),
) -> Principal:
    token = extract_bearer_token(authorization)
    principal = principal_for_token(token)
    if principal is None:
        raise HTTPException(status_code=401, detail="invalid or missing credentials")
    return principal


def require_any_role(*roles: str):
    async def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.has_any_role(*roles):
            raise HTTPException(status_code=403, detail="forbidden")
        return principal

    return dependency


def principal_from_websocket(websocket: WebSocket) -> Principal | None:
    token = extract_bearer_token(websocket.headers.get("authorization"))
    return principal_for_token(token)
