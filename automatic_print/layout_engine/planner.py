from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .images import target_size
from .labels import format_label, label_badge, label_layout
from .models import LayoutSettings, Placement, ProgressCallback, mm_to_px


def _signed_mm(value: float, dpi: int) -> int:
    pixels = mm_to_px(abs(value), dpi)
    return -pixels if value < 0 else pixels


def plan_layout(
    paths: list[Path],
    settings: LayoutSettings,
    progress: ProgressCallback | None,
) -> tuple[list[tuple[Path, Placement]], dict[int, str], int, int]:
    canvas_width = mm_to_px(settings.media_width_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    usable_width = canvas_width - 2 * margin
    if usable_width <= 0:
        raise ValueError("外边距过大，画布没有可打印区域。")
    gap = mm_to_px(settings.number_gap_mm, settings.dpi)
    offset_x = _signed_mm(settings.label_offset_x_mm, settings.dpi)
    offset_y = _signed_mm(settings.label_offset_y_mm, settings.dpi)
    planned: list[tuple[Path, Placement]] = []
    labels: dict[int, str] = {}
    x = y = margin
    row_height = 0
    created_at = datetime.now().astimezone()
    for index, path in enumerate(paths, start=1):
        width, height = target_size(path, settings.dpi)
        label_width = label_height = 0
        image_rx = image_ry = label_rx = label_ry = 0
        footprint_width, footprint_height = width, height
        if settings.number_images:
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
            (
                image_rx,
                image_ry,
                label_rx,
                label_ry,
                footprint_width,
                footprint_height,
            ) = label_layout(
                (width, height),
                (label_width, label_height),
                settings.label_position,
                gap,
                offset_x,
                offset_y,
            )
        if footprint_width > usable_width:
            raise ValueError(f"图片 {path.name} 的宽度超过了材料可打印宽度。")
        if x > margin and x + footprint_width > canvas_width - margin:
            x = margin
            y += row_height + spacing
            row_height = 0
        placement = Placement(
            path.name,
            index,
            x + image_rx,
            y + image_ry,
            width,
            height,
            x + label_rx,
            y + label_ry,
            label_width,
            label_height,
            y,
            footprint_width,
            footprint_height,
        )
        planned.append((path, placement))
        x += footprint_width + spacing
        row_height = max(row_height, footprint_height)
        if progress:
            progress("读取图片尺寸", index, len(paths), path.name)
    if not planned:
        raise ValueError("没有可供排版的图片。")
    return planned, labels, canvas_width, y + row_height + margin
