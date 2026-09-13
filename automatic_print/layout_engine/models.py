from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


ProgressCallback = Callable[[str, int, int, str], None]


@dataclass(frozen=True)
class LayoutSettings:
    media_width_mm: float = 450
    spacing_mm: float = 8
    margin_mm: float = 3
    dpi: int = 300
    png_compression_level: int = 1
    png_engine: str = "pillow"
    worker_threads: int = 8
    number_images: bool = True
    number_gap_mm: float = 5
    number_font_size_mm: float = 10
    label_text_template: str = "{编号}"
    label_position: str = "bottom"
    label_offset_x_mm: float = 0
    label_offset_y_mm: float = 0
    label_date_format: str = "%Y-%m-%d"
    label_follow_qr: bool = True
    allow_rotation: bool = True
    rotation_direction: str = "left"
    color_block_enabled: bool = True
    color_block_color: str = "#ff0000"
    color_block_width_mm: float = 10
    color_block_height_mm: float = 10
    color_block_position: str = "left_top"
    color_block_gap_mm: float = 5
    color_block_offset_x_mm: float = 0
    color_block_offset_y_mm: float = 0
    cutter_mode: str = "free"
    cutter_knife_mm: float = 300
    cutter_safety_mm: float = 3
    cutter_marker_offset_mm: float = 0


@dataclass(frozen=True)
class Placement:
    source: str
    sequence_number: int
    x_px: int
    y_px: int
    width_px: int
    height_px: int
    number_x_px: int
    number_y_px: int
    number_width_px: int
    number_height_px: int
    row_y_px: int
    footprint_width_px: int
    footprint_height_px: int
    rotation_degrees: int = 0
    color_block_x_px: int = 0
    color_block_y_px: int = 0
    color_block_width_px: int = 0
    color_block_height_px: int = 0


def mm_to_px(value: float, dpi: int) -> int:
    return max(0, round(value * dpi / 25.4))
