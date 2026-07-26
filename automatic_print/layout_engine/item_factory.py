from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .images import target_size
from .labels import format_label, label_badge, label_layout
from .models import LayoutSettings, mm_to_px


@dataclass(frozen=True)
class LayoutItem:
    path: Path
    index: int
    width: int
    height: int
    image_rx: int
    image_ry: int
    label_rx: int
    label_ry: int
    label_width: int
    label_height: int
    footprint_width: int
    footprint_height: int
    rotation_degrees: int


def read_items(paths, settings, progress):
    if not paths:
        raise ValueError("没有可供排版的图片。")
    labels, items = {}, []
    created_at = datetime.now().astimezone()
    gap = mm_to_px(settings.number_gap_mm, settings.dpi)
    offset_x = _signed_mm(settings.label_offset_x_mm, settings.dpi)
    offset_y = _signed_mm(settings.label_offset_y_mm, settings.dpi)
    for index, path in enumerate(paths, start=1):
        width, height = target_size(path, settings.dpi)
        choices = [
            _make_item(
                path, index, width, height, settings, labels,
                created_at, gap, offset_x, offset_y, 0,
            )
        ]
        if settings.allow_rotation and width != height:
            degrees = 90 if settings.rotation_direction == "left" else -90
            choices.append(
                _make_item(
                    path, index, height, width, settings, labels,
                    created_at, gap, offset_x, offset_y, degrees,
                )
            )
        items.append(choices)
        if progress:
            progress("读取图片尺寸", index, len(paths), path.name)
    return items, labels


def _make_item(
    path, index, width, height, settings, labels,
    created_at, gap, offset_x, offset_y, rotation_degrees,
):
    values = _label_values(
        path, index, width, height, settings, labels,
        created_at, gap, offset_x, offset_y,
    )
    return LayoutItem(
        path, index, width, height, *values, rotation_degrees
    )


def _label_values(
    path, index, width, height, settings, labels,
    created_at, gap, offset_x, offset_y,
):
    if not settings.number_images:
        return 0, 0, 0, 0, 0, 0, width, height
    text = format_label(
        settings.label_text_template,
        index,
        path,
        created_at,
        settings.label_date_format,
    )
    labels[index] = text
    badge = label_badge(
        text, settings.dpi, settings.number_font_size_mm
    )
    label_width, label_height = badge.size
    badge.close()
    layout = label_layout(
        (width, height),
        (label_width, label_height),
        settings.label_position,
        gap,
        offset_x,
        offset_y,
    )
    return *layout[:4], label_width, label_height, *layout[4:]


def _signed_mm(value: float, dpi: int) -> int:
    pixels = mm_to_px(abs(value), dpi)
    return -pixels if value < 0 else pixels
