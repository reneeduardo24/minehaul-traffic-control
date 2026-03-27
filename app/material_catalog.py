from __future__ import annotations

from copy import deepcopy

MATERIALS = [
    {
        "id": "copper_ore",
        "label": "Mineral de cobre",
        "short_label": "Cobre",
        "accent": "#d68624",
        "icon": "ore",
    },
    {
        "id": "waste_rock",
        "label": "Roca esteril",
        "short_label": "Esteril",
        "accent": "#97a3b6",
        "icon": "waste",
    },
]

MATERIAL_BY_ID = {material["id"]: material for material in MATERIALS}
VALID_MATERIAL_IDS = set(MATERIAL_BY_ID)


def materials_payload() -> list[dict[str, str]]:
    return deepcopy(MATERIALS)
