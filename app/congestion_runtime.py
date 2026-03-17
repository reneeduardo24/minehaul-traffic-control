from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CongestionRuntime:
    zone_slow_since: dict[str, datetime] = field(default_factory=dict)
    congestion_active: set[str] = field(default_factory=set)

    def evaluate(self, positions: list[dict]) -> dict | None:
        if not positions:
            return None
        zone_id = positions[0]["zone_id"]
        avg_speed = sum(v["speed"] for v in positions) / len(positions)
        now = datetime.now(timezone.utc)
        if len(positions) >= 3 and avg_speed <= 1.0:
            self.zone_slow_since.setdefault(zone_id, now)
            duration = int((now - self.zone_slow_since[zone_id]).total_seconds())
            if duration >= 5 and zone_id not in self.congestion_active:
                self.congestion_active.add(zone_id)
                severity = "HIGH" if len(positions) >= 5 else "MEDIUM"
                return {
                    "zone_id": zone_id,
                    "vehicle_count": len(positions),
                    "avg_speed": round(avg_speed, 2),
                    "duration_seconds": duration,
                    "severity": severity,
                }
        else:
            self.zone_slow_since.pop(zone_id, None)
            self.congestion_active.discard(zone_id)
        return None

    def clear_zone(self, zone_id: str) -> None:
        self.zone_slow_since.pop(zone_id, None)
        self.congestion_active.discard(zone_id)
