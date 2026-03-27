from __future__ import annotations

from copy import deepcopy

from .material_catalog import materials_payload

WORLD = {
    "min_x": 0.0,
    "min_y": 0.0,
    "max_x": 24.0,
    "max_y": 10.0,
}

ZONES = [
    {
        "id": "Z1",
        "label": "Pit Zone",
        "x": 0.0,
        "y": 0.0,
        "width": 8.0,
        "height": 10.0,
        "speed_limit": 1.35,
    },
    {
        "id": "Z2",
        "label": "Transit Corridor",
        "x": 8.0,
        "y": 0.0,
        "width": 8.0,
        "height": 10.0,
        "speed_limit": 1.2,
    },
    {
        "id": "Z3",
        "label": "Processing Zone",
        "x": 16.0,
        "y": 0.0,
        "width": 8.0,
        "height": 10.0,
        "speed_limit": 1.45,
    },
]

FACILITIES = [
    {
        "id": "PIT-A",
        "kind": "pit",
        "label": "PIT-A",
        "x": 2.0,
        "y": 8.4,
        "zone_id": "Z1",
        "label_dx": 0.0,
        "label_dy": 0.3,
        "label_anchor": "middle",
    },
    {
        "id": "PIT-B",
        "kind": "pit",
        "label": "PIT-B",
        "x": 1.8,
        "y": 6.0,
        "zone_id": "Z1",
        "label_dx": 1.1,
        "label_dy": 0.0,
        "label_anchor": "start",
    },
    {
        "id": "ORE-DEPOT-1",
        "kind": "depot",
        "label": "ORE DEPOT-1",
        "x": 1.9,
        "y": 3.8,
        "zone_id": "Z1",
        "label_dx": 1.25,
        "label_dy": -0.95,
        "label_anchor": "start",
    },
    {
        "id": "PIT-C",
        "kind": "pit",
        "label": "PIT-C",
        "x": 2.0,
        "y": 1.4,
        "zone_id": "Z1",
        "label_dx": 1.1,
        "label_dy": 0.0,
        "label_anchor": "start",
    },
    {
        "id": "CRUSHER-B",
        "kind": "crusher",
        "label": "CRUSHER-B",
        "x": 21.0,
        "y": 8.4,
        "zone_id": "Z3",
        "label_dx": -1.1,
        "label_dy": 0.3,
        "label_anchor": "end",
    },
    {
        "id": "PAD-D",
        "kind": "stockpile",
        "label": "PAD-D",
        "x": 21.4,
        "y": 6.0,
        "zone_id": "Z3",
        "label_dx": -1.2,
        "label_dy": 0.0,
        "label_anchor": "end",
    },
    {
        "id": "STORAGE-DEPOT-2",
        "kind": "storage",
        "label": "STORAGE DEPOT-2",
        "x": 20.9,
        "y": 3.6,
        "zone_id": "Z3",
        "label_dx": -1.15,
        "label_dy": -0.92,
        "label_anchor": "end",
    },
    {
        "id": "DUMP-2",
        "kind": "dump",
        "label": "DUMP-2",
        "x": 20.8,
        "y": 1.4,
        "zone_id": "Z3",
        "label_dx": -1.0,
        "label_dy": 0.0,
        "label_anchor": "end",
    },
]

TRAFFIC_LIGHTS = [
    {
        "id": "TL-01",
        "label": "West Collector Cross",
        "zone_id": "Z1",
        "x": 6.0,
        "y": 3.8,
        "default_state": "GREEN",
        "label_dx": 0.0,
        "label_dy": 1.3,
        "label_anchor": "middle",
    },
    {
        "id": "TL-02",
        "label": "Transit Crown Split",
        "zone_id": "Z2",
        "x": 12.1,
        "y": 6.8,
        "default_state": "GREEN",
        "label_dx": 0.0,
        "label_dy": 1.45,
        "label_anchor": "middle",
    },
    {
        "id": "TL-03",
        "label": "East Dispatch Cross",
        "zone_id": "Z3",
        "x": 14.9,
        "y": 3.8,
        "default_state": "GREEN",
        "label_dx": 0.0,
        "label_dy": 1.3,
        "label_anchor": "middle",
    },
    {
        "id": "TL-04",
        "label": "South Bypass Merge",
        "zone_id": "Z2",
        "x": 10.0,
        "y": 3.8,
        "default_state": "GREEN",
        "label_dx": 0.0,
        "label_dy": -1.15,
        "label_anchor": "middle",
    },
]

ROADS = [
    {
        "id": "road-north-crown",
        "label": "North Crown Haul",
        "kind": "primary",
        "waypoints": [
            {"x": 2.0, "y": 8.4},
            {"x": 6.6, "y": 8.4},
            {"x": 9.2, "y": 8.4},
            {"x": 12.1, "y": 6.8},
            {"x": 16.4, "y": 8.4},
            {"x": 21.0, "y": 8.4},
        ],
    },
    {
        "id": "road-west-bench",
        "label": "West Bench Transfer",
        "kind": "collector",
        "waypoints": [
            {"x": 1.8, "y": 6.0},
            {"x": 4.3, "y": 6.0},
            {"x": 7.5, "y": 6.0},
            {"x": 10.4, "y": 5.9},
            {"x": 12.1, "y": 6.8},
        ],
    },
    {
        "id": "road-west-collector",
        "label": "West Collector",
        "kind": "collector",
        "waypoints": [
            {"x": 6.0, "y": 1.4},
            {"x": 6.0, "y": 3.8},
            {"x": 6.0, "y": 6.0},
        ],
    },
    {
        "id": "road-mid-spine",
        "label": "Ore Spine",
        "kind": "primary",
        "waypoints": [
            {"x": 1.9, "y": 3.8},
            {"x": 6.0, "y": 3.8},
            {"x": 10.0, "y": 3.8},
            {"x": 14.9, "y": 3.8},
            {"x": 18.2, "y": 3.8},
            {"x": 20.9, "y": 3.8},
        ],
    },
    {
        "id": "road-south-ramp",
        "label": "South Ramp",
        "kind": "branch",
        "waypoints": [
            {"x": 2.0, "y": 1.4},
            {"x": 4.5, "y": 1.4},
            {"x": 6.0, "y": 1.4},
        ],
    },
    {
        "id": "road-south-bypass",
        "label": "South Bypass",
        "kind": "collector",
        "waypoints": [
            {"x": 10.0, "y": 3.8},
            {"x": 10.8, "y": 2.5},
            {"x": 12.4, "y": 1.6},
            {"x": 14.9, "y": 1.4},
        ],
    },
    {
        "id": "road-east-pad",
        "label": "Pad Transfer",
        "kind": "branch",
        "waypoints": [
            {"x": 12.1, "y": 6.8},
            {"x": 14.9, "y": 6.0},
            {"x": 18.0, "y": 6.0},
            {"x": 21.4, "y": 6.0},
        ],
    },
    {
        "id": "road-east-collector",
        "label": "East Collector",
        "kind": "collector",
        "waypoints": [
            {"x": 14.9, "y": 1.4},
            {"x": 14.9, "y": 3.8},
            {"x": 14.9, "y": 6.0},
        ],
    },
    {
        "id": "road-east-dump",
        "label": "Dump Return",
        "kind": "branch",
        "waypoints": [
            {"x": 14.9, "y": 1.4},
            {"x": 18.0, "y": 1.4},
            {"x": 20.8, "y": 1.4},
        ],
    },
]

ROUTES = [
    {
        "id": "loop_pit_a_crusher_b",
        "label": "PIT-A to CRUSHER-B loop",
        "origin": "PIT-A",
        "destination": "CRUSHER-B",
        "delivery_point_index": 5,
        "controls": [
            {"traffic_light_id": "TL-02", "stop_point_index": 3},
            {"traffic_light_id": "TL-02", "stop_point_index": 7},
        ],
        "waypoints": [
            {"x": 2.0, "y": 8.4},
            {"x": 6.6, "y": 8.4},
            {"x": 9.2, "y": 8.4},
            {"x": 12.1, "y": 6.8},
            {"x": 16.4, "y": 8.4},
            {"x": 21.0, "y": 8.4},
            {"x": 16.4, "y": 8.4},
            {"x": 12.1, "y": 6.8},
            {"x": 9.2, "y": 8.4},
            {"x": 6.6, "y": 8.4},
            {"x": 2.0, "y": 8.4},
        ],
    },
    {
        "id": "loop_pit_b_pad_d",
        "label": "PIT-B to PAD-D loop",
        "origin": "PIT-B",
        "destination": "PAD-D",
        "delivery_point_index": 7,
        "controls": [
            {"traffic_light_id": "TL-02", "stop_point_index": 4},
            {"traffic_light_id": "TL-03", "stop_point_index": 10},
            {"traffic_light_id": "TL-04", "stop_point_index": 11},
            {"traffic_light_id": "TL-01", "stop_point_index": 12},
        ],
        "waypoints": [
            {"x": 1.8, "y": 6.0},
            {"x": 4.3, "y": 6.0},
            {"x": 7.5, "y": 6.0},
            {"x": 10.4, "y": 5.9},
            {"x": 12.1, "y": 6.8},
            {"x": 14.9, "y": 6.0},
            {"x": 18.0, "y": 6.0},
            {"x": 21.4, "y": 6.0},
            {"x": 18.0, "y": 6.0},
            {"x": 14.9, "y": 6.0},
            {"x": 14.9, "y": 3.8},
            {"x": 10.0, "y": 3.8},
            {"x": 6.0, "y": 3.8},
            {"x": 6.0, "y": 6.0},
            {"x": 4.3, "y": 6.0},
            {"x": 1.8, "y": 6.0},
        ],
    },
    {
        "id": "loop_ore_depot_storage",
        "label": "ORE-DEPOT-1 to STORAGE-DEPOT-2 loop",
        "origin": "ORE-DEPOT-1",
        "destination": "STORAGE-DEPOT-2",
        "delivery_point_index": 5,
        "controls": [
            {"traffic_light_id": "TL-01", "stop_point_index": 1},
            {"traffic_light_id": "TL-04", "stop_point_index": 2},
            {"traffic_light_id": "TL-03", "stop_point_index": 3},
            {"traffic_light_id": "TL-03", "stop_point_index": 7},
            {"traffic_light_id": "TL-01", "stop_point_index": 11},
        ],
        "waypoints": [
            {"x": 1.9, "y": 3.8},
            {"x": 6.0, "y": 3.8},
            {"x": 10.0, "y": 3.8},
            {"x": 14.9, "y": 3.8},
            {"x": 20.9, "y": 3.8},
            {"x": 20.9, "y": 3.6},
            {"x": 20.9, "y": 3.8},
            {"x": 14.9, "y": 3.8},
            {"x": 14.9, "y": 1.4},
            {"x": 10.0, "y": 1.4},
            {"x": 6.0, "y": 1.4},
            {"x": 6.0, "y": 3.8},
            {"x": 1.9, "y": 3.8},
        ],
    },
    {
        "id": "loop_pit_c_dump_2",
        "label": "PIT-C to DUMP-2 loop",
        "origin": "PIT-C",
        "destination": "DUMP-2",
        "delivery_point_index": 8,
        "controls": [
            {"traffic_light_id": "TL-01", "stop_point_index": 3},
            {"traffic_light_id": "TL-04", "stop_point_index": 4},
            {"traffic_light_id": "TL-03", "stop_point_index": 11},
            {"traffic_light_id": "TL-04", "stop_point_index": 12},
            {"traffic_light_id": "TL-01", "stop_point_index": 13},
        ],
        "waypoints": [
            {"x": 2.0, "y": 1.4},
            {"x": 4.5, "y": 1.4},
            {"x": 6.0, "y": 1.4},
            {"x": 6.0, "y": 3.8},
            {"x": 10.0, "y": 3.8},
            {"x": 12.4, "y": 1.6},
            {"x": 14.9, "y": 1.4},
            {"x": 18.0, "y": 1.4},
            {"x": 20.8, "y": 1.4},
            {"x": 18.0, "y": 1.4},
            {"x": 14.9, "y": 1.4},
            {"x": 14.9, "y": 3.8},
            {"x": 10.0, "y": 3.8},
            {"x": 6.0, "y": 3.8},
            {"x": 6.0, "y": 1.4},
            {"x": 4.5, "y": 1.4},
            {"x": 2.0, "y": 1.4},
        ],
    },
]

VALID_ZONE_IDS = {zone["id"] for zone in ZONES}
VALID_FACILITY_IDS = {facility["id"] for facility in FACILITIES}
ROUTE_BY_ID = {route["id"]: route for route in ROUTES}


def build_default_traffic_lights() -> dict[str, dict[str, str | float]]:
    return {
        light["id"]: {
            "zone_id": light["zone_id"],
            "state": light["default_state"],
            "x": light["x"],
            "y": light["y"],
            "label": light["label"],
            "label_dx": light["label_dx"],
            "label_dy": light["label_dy"],
            "label_anchor": light["label_anchor"],
        }
        for light in TRAFFIC_LIGHTS
    }


def detect_zone_id(x: float, y: float) -> str:
    for zone in ZONES:
        if zone["x"] <= x <= zone["x"] + zone["width"] and zone["y"] <= y <= zone["y"] + zone["height"]:
            return zone["id"]
    nearest = min(ZONES, key=lambda zone: abs((zone["x"] + zone["width"] / 2) - x))
    return nearest["id"]


def topology_payload() -> dict:
    return {
        "world": deepcopy(WORLD),
        "zones": deepcopy(ZONES),
        "facilities": deepcopy(FACILITIES),
        "traffic_lights": deepcopy(TRAFFIC_LIGHTS),
        "roads": deepcopy(ROADS),
        "routes": deepcopy(ROUTES),
        "materials": materials_payload(),
    }
