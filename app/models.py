from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from .material_catalog import VALID_MATERIAL_IDS
from .topology import VALID_FACILITY_IDS, VALID_ZONE_IDS


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
    material_type: str | None = None

    @field_validator("zone_id")
    @classmethod
    def validate_zone_id(cls, value: str) -> str:
        if value not in VALID_ZONE_IDS:
            raise ValueError(f"invalid zone_id: {value}")
        return value

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        if value not in VALID_FACILITY_IDS:
            raise ValueError(f"invalid destination: {value}")
        return value

    @field_validator("material_type")
    @classmethod
    def validate_material_type(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_MATERIAL_IDS:
            raise ValueError(f"invalid material_type: {value}")
        return value


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

    @field_validator("origin", "destination")
    @classmethod
    def validate_facility(cls, value: str) -> str:
        if value not in VALID_FACILITY_IDS:
            raise ValueError(f"invalid facility: {value}")
        return value

    @field_validator("quantity_tons")
    @classmethod
    def validate_quantity(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("quantity_tons must be greater than 0")
        return value

    @field_validator("material_type")
    @classmethod
    def validate_material_type(cls, value: str) -> str:
        if value not in VALID_MATERIAL_IDS:
            raise ValueError(f"invalid material_type: {value}")
        return value


class TrafficLightCommand(BaseModel):
    traffic_light_id: str
    new_state: TrafficLightState
    changed_by: str = "central-operator"


class ZoneEvaluationRequest(BaseModel):
    zone_id: str

    @field_validator("zone_id")
    @classmethod
    def validate_zone_id(cls, value: str) -> str:
        if value not in VALID_ZONE_IDS:
            raise ValueError(f"invalid zone_id: {value}")
        return value


class TopologyResponse(BaseModel):
    world: dict[str, float]
    zones: list[dict[str, Any]]
    facilities: list[dict[str, Any]]
    traffic_lights: list[dict[str, Any]]
    roads: list[dict[str, Any]]
    routes: list[dict[str, Any]]
    materials: list[dict[str, Any]]
