"""Recognize UV material from explicit production SKU codes, not platform ownership."""

import re

from .sheet import UV_MATERIAL_BY_KEY


SKU_MATERIAL_KEYS = {
    "tie_1040": "1040",
    "tie_2030": "2030_iron",
    "lv_2030": "2030_aluminum",
    "muban_2030": "2030_wood",
    "tie_yuan_2020": "round_iron",
    "lv_yuan_2020": "raw_aluminum",
    "tie_3040": "3040",
    "guazhong_2525": "clock_2525",
    "guazhong_3030": "clock_3030",
    "chepai": "license_plate",
    "yakeli": "acrylic",
}

LABEL_MATERIAL_KEYS = {
    spec.label.casefold(): spec.key
    for spec in UV_MATERIAL_BY_KEY.values()
    if not spec.label.isdigit()
}


def identify_uv_batch_material(batch_name):
    """Return a unique catalog spec only when the name carries a known UV SKU."""
    normalized = re.sub(r"[^\w]+", "_", str(batch_name).casefold()).strip("_")
    candidates = set()
    for code, key in SKU_MATERIAL_KEYS.items():
        if re.search(rf"(?:^|_){re.escape(code)}(?:_|$)", normalized):
            candidates.add(key)
    for label, key in LABEL_MATERIAL_KEYS.items():
        if re.search(rf"(?:^|_){re.escape(label)}(?:_|$)", normalized):
            candidates.add(key)
    if len(candidates) != 1:
        return None
    return UV_MATERIAL_BY_KEY[next(iter(candidates))]
