from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


ProgressCallback = Callable[[str, int, int, str], None]


@dataclass(frozen=True)
class LayoutSettings:
    media_width_mm: float = 600
    spacing_mm: float = 3
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


def mm_to_px(value: float, dpi: int) -> int:
    return max(0, round(value * dpi / 25.4))
