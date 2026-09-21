"""UV fixed-sheet layout entry points."""

from .render import generate_uv_sheet
from .material_codes import identify_uv_batch_material
from .sheet import (
    UV_2030_LANDSCAPE,
    UV_MATERIALS,
    UV_MATERIAL_BY_KEY,
    plan_uv_sheet,
    uv_sheet_capacity,
)

__all__ = [
    "UV_2030_LANDSCAPE",
    "UV_MATERIALS",
    "UV_MATERIAL_BY_KEY",
    "generate_uv_sheet",
    "identify_uv_batch_material",
    "plan_uv_sheet",
    "uv_sheet_capacity",
]
