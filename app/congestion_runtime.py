from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import CongestionPayload, CongestionSeverity, EventType


@dataclass
class CongestionRuntime:
    vehicle_positions: dict[str, dict] = field(default_factory=dict)
    zone_slow_since: dict[str, datetime] = field(default_factory=dict)
    active_congestions: dict[str, dict] = field(default_factory=dict)

    def load_positions(self, positions: list[dict]) -> None:
        self.vehicle_positions = {item["vehicle_id"]: item for item in positions}

    def load_active_congestions(self, active_items: list[dict]) -> None:
        self.active_congestions = {item["zone_id"]: item for item in active_items}

    def get_active_congestions(self) -> dict[str, dict]:
        return self.active_congestions

    def apply_position(self, position: dict) -> list[tuple[EventType, CongestionPayload]]:
        previous_zone = self.vehicle_positions.get(position["vehicle_id"], {}).get("zone_id")
        self.vehicle_positions[position["vehicle_id"]] = position

        events: list[tuple[EventType, CongestionPayload]] = []
        zones_to_evaluate = {position["zone_id"]}
        if previous_zone and previous_zone != position["zone_id"]:
            zones_to_evaluate.add(previous_zone)

        for zone_id in zones_to_evaluate:
            result = self.evaluate_zone(zone_id)
            if result is not None:
                events.append(result)
        return events

    def evaluate_zone(self, zone_id: str) -> tuple[EventType, CongestionPayload] | None:
        positions = [
            item for item in self.vehicle_positions.values() if item.get("zone_id") == zone_id
        ]
        now = datetime.now(timezone.utc)

        if not positions:
            self.zone_slow_since.pop(zone_id, None)
            active = self.active_congestions.pop(zone_id, None)
            if active is None:
                return None
            payload = CongestionPayload(
                zone_id=zone_id,
                vehicle_count=0,
                avg_speed=0.0,
                duration_seconds=active.get("duration_seconds", 0),
                severity=CongestionSeverity(active.get("severity", "LOW")),
                active=False,
                occurred_at=now,
            )
            return EventType.CONGESTION_CLEARED, payload

        avg_speed = sum(item["speed"] for item in positions) / len(positions)
        qualifies = len(positions) >= 3 and avg_speed <= 1.0
        if qualifies:
            self.zone_slow_since.setdefault(zone_id, now)
            duration = int((now - self.zone_slow_since[zone_id]).total_seconds())
            if duration >= 5 and zone_id not in self.active_congestions:
                severity = (
                    CongestionSeverity.HIGH
                    if len(positions) >= 5
                    else CongestionSeverity.MEDIUM
                )
                payload = CongestionPayload(
                    zone_id=zone_id,
                    vehicle_count=len(positions),
                    avg_speed=round(avg_speed, 2),
                    duration_seconds=duration,
                    severity=severity,
                    active=True,
                    occurred_at=now,
                )
                self.active_congestions[zone_id] = payload.model_dump(mode="json")
                return EventType.CONGESTION_DETECTED, payload
            if zone_id in self.active_congestions:
                self.active_congestions[zone_id] = {
                    **self.active_congestions[zone_id],
                    "vehicle_count": len(positions),
                    "avg_speed": round(avg_speed, 2),
                    "duration_seconds": duration,
                    "updated_at": now.isoformat(),
                }
            return None

        self.zone_slow_since.pop(zone_id, None)
        active = self.active_congestions.pop(zone_id, None)
        if active is None:
            return None
        payload = CongestionPayload(
            zone_id=zone_id,
            vehicle_count=len(positions),
            avg_speed=round(avg_speed, 2),
            duration_seconds=active.get("duration_seconds", 0),
            severity=CongestionSeverity(active.get("severity", "LOW")),
            active=False,
            occurred_at=now,
        )
        return EventType.CONGESTION_CLEARED, payload
