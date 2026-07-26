from __future__ import annotations

from pathlib import Path

from .item_factory import read_items
from .metrics import basic_ordered_height
from .models import LayoutSettings, Placement, ProgressCallback, mm_to_px
from .row_optimizer import optimal_ordered_layout
from .units import build_units, optimizer_options


def plan_layout(
    paths: list[Path],
    settings: LayoutSettings,
    progress: ProgressCallback | None,
) -> tuple[list[tuple[Path, Placement]], dict[int, str], int, int, int]:
    canvas_width = mm_to_px(settings.media_width_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    usable_width = canvas_width - 2 * margin
    if usable_width <= 0:
        raise ValueError("外边距过大，画布没有可打印区域。")
    items, labels = read_items(paths, settings, progress)
    units = build_units(items, spacing)
    double_count = sum(
        len(choices[0].members) == 2 for choices in units
    )
    if progress and double_count:
        progress(
            "整理双面图片",
            double_count,
            double_count,
            f"已识别 {double_count} 组双面图片",
        )
    for choices in units:
        if all(choice.width > usable_width for choice in choices):
            name = choices[0].members[0].item.path.name
            raise ValueError(f"图片组 {name} 超过了材料可打印宽度。")
    rows = optimal_ordered_layout(
        optimizer_options(units), usable_width, spacing
    )
    planned = _place_rows(units, rows, margin, spacing)
    canvas_height = (
        max(
            placement.row_y_px + placement.footprint_height_px
            for _path, placement in planned
        )
        + margin
    )
    baseline = [_baseline_choice(choices, usable_width) for choices in units]
    baseline_height = (
        basic_ordered_height(baseline, usable_width, spacing) + 2 * margin
    )
    return planned, labels, canvas_width, canvas_height, baseline_height


def _baseline_choice(choices, usable_width):
    fitting = next(
        (choice for choice in choices if choice.width <= usable_width),
        None,
    )
    if fitting is None:
        raise ValueError("至少一个图片组超过了材料可打印宽度。")
    return fitting.width, fitting.height


def _place_rows(units, rows, margin, spacing):
    planned, y = [], margin
    for start, end, choice_indexes in rows:
        row = [
            units[index][choice]
            for index, choice in zip(
                range(start, end), choice_indexes, strict=True
            )
        ]
        row_height = max(choice.height for choice in row)
        x = margin
        for choice in row:
            planned.extend(_place_choice(choice, x, y))
            x += choice.width + spacing
        y += row_height + spacing
    return planned


def _place_choice(choice, unit_x, row_y):
    placed = []
    for member in choice.members:
        item = member.item
        base_x, base_y = unit_x + member.x, row_y + member.y
        placed.append(
            (
                item.path,
                Placement(
                    item.path.name,
                    item.index,
                    base_x + item.image_rx,
                    base_y + item.image_ry,
                    item.width,
                    item.height,
                    base_x + item.label_rx,
                    base_y + item.label_ry,
                    item.label_width,
                    item.label_height,
                    row_y,
                    choice.width,
                    choice.height,
                    item.rotation_degrees,
                ),
            )
        )
    return placed
