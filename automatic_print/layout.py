"""Public compatibility facade for the modular layout engine."""

from .layout_engine.discovery import discover_images, discovered_extensions
from .layout_engine.labels import format_label as _format_label
from .layout_engine.models import LayoutSettings, Placement, mm_to_px
from .layout_engine.service import generate_layout, png_engine_name

__all__ = [
    "LayoutSettings",
    "Placement",
    "discover_images",
    "discovered_extensions",
    "generate_layout",
    "mm_to_px",
    "png_engine_name",
]
