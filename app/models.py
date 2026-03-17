from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class TrafficLightState(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class EventEnvelope(BaseModel):
    event_type: str
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    payload: dict[str, Any]


class VehiclePositionPayload(BaseModel):
    vehicle_id: str
    zone_id: str
    x: float
    y: float
    speed: float
    destination: str


class TrafficLightChangedPayload(BaseModel):
    traffic_light_id: str
    zone_id: str
    previous_state: TrafficLightState
    new_state: TrafficLightState
    changed_by: str


class CongestionPayload(BaseModel):
    zone_id: str
    vehicle_count: int
    avg_speed: float
    duration_seconds: int
    severity: Literal["LOW", "MEDIUM", "HIGH"]


class MaterialDelivery(BaseModel):
    delivery_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    vehicle_id: str
    origin: str
    destination: str
    material_type: str
    quantity_tons: float


class TrafficLightCommand(BaseModel):
    traffic_light_id: str
    new_state: TrafficLightState
    changed_by: str = "central-operator"
