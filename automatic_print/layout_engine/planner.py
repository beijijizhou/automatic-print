from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .images import target_size
from .labels import format_label, label_badge, label_layout
from .models import LayoutSettings, Placement, ProgressCallback, mm_to_px
from .row_optimizer import optimal_ordered_layout


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
    items, labels = _read_items(paths, settings, progress)
    for choices in items:
        if all(item.footprint_width > usable_width for item in choices):
            raise ValueError(
                f"图片 {choices[0].path.name} 的宽度超过了材料可打印宽度。"
            )
    rows = optimal_ordered_layout(
        [
            [
                (item.footprint_width, item.footprint_height)
                for item in choices
            ]
            for choices in items
        ],
        usable_width,
        spacing,
    )
    planned = _place_rows(items, rows, margin, spacing)
    canvas_height = (
        max(
            placement.row_y_px + placement.footprint_height_px
            for _path, placement in planned
        )
        + margin
    )
    return planned, labels, canvas_width, canvas_height


def _read_items(paths, settings, progress):
    if not paths:
        raise ValueError("没有可供排版的图片。")
    labels = {}
    items = []
    created_at = datetime.now().astimezone()
    gap = mm_to_px(settings.number_gap_mm, settings.dpi)
    offset_x = _signed_mm(settings.label_offset_x_mm, settings.dpi)
    offset_y = _signed_mm(settings.label_offset_y_mm, settings.dpi)
    for index, path in enumerate(paths, start=1):
        width, height = target_size(path, settings.dpi)
        natural = _make_item(
            path,
            index,
            width,
            height,
            settings,
            labels,
            created_at,
            gap,
            offset_x,
            offset_y,
            0,
        )
        choices = [natural]
        if settings.allow_rotation and width != height:
            degrees = 90 if settings.rotation_direction == "left" else -90
            choices.append(
                _make_item(
                    path,
                    index,
                    height,
                    width,
                    settings,
                    labels,
                    created_at,
                    gap,
                    offset_x,
                    offset_y,
                    degrees,
                )
            )
        items.append(choices)
        if progress:
            progress("读取图片尺寸", index, len(paths), path.name)
    return items, labels


def _make_item(
    path,
    index,
    width,
    height,
    settings,
    labels,
    created_at,
    gap,
    offset_x,
    offset_y,
    rotation_degrees,
):
    values = _label_values(
        path,
        index,
        width,
        height,
        settings,
        labels,
        created_at,
        gap,
        offset_x,
        offset_y,
    )
    return LayoutItem(
        path, index, width, height, *values, rotation_degrees
    )


def _label_values(
    path,
    index,
    width,
    height,
    settings,
    labels,
    created_at,
    gap,
    offset_x,
    offset_y,
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


def _place_rows(items, rows, margin, spacing):
    planned = []
    y = margin
    for start, end, choice_indexes in rows:
        row = [
            items[index][choice]
            for index, choice in zip(
                range(start, end), choice_indexes, strict=True
            )
        ]
        row_height = max(item.footprint_height for item in row)
        x = margin
        for item in row:
            planned.append(
                (
                    item.path,
                    Placement(
                        item.path.name,
                        item.index,
                        x + item.image_rx,
                        y + item.image_ry,
                        item.width,
                        item.height,
                        x + item.label_rx,
                        y + item.label_ry,
                        item.label_width,
                        item.label_height,
                        y,
                        item.footprint_width,
                        item.footprint_height,
                        item.rotation_degrees,
                    ),
                )
            )
            x += item.footprint_width + spacing
        y += row_height + spacing
    return planned
