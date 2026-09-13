from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from .order_groups import ordered_paths
from .batch_analysis import analyze_batch, finish_analysis

from .item_factory import read_items
from .metrics import basic_ordered_height
from .models import LayoutSettings, Placement, ProgressCallback, mm_to_px
from .row_optimizer import optimal_ordered_layout
from .units import build_units, optimizer_options


def plan_layout(
    paths: list[Path],
    settings: LayoutSettings,
    progress: ProgressCallback | None,
    analysis_ready=None,
) -> tuple[list[tuple[Path, Placement]], dict[int, str], int, int, int]:
    settings = replace(settings, sequence_numbers=settings.sequence_numbers or
                       tuple((str(path.resolve()), i) for i, path in enumerate(paths, 1)))
    paths = ordered_paths(paths)
    analysis = analyze_batch(paths, settings, progress, analysis_ready)
    result = _plan_layout(paths, settings, progress, analysis, analysis_ready)
    if analysis_ready:
        analysis_ready(finish_analysis(analysis, result[0], settings, result[3], result[4]))
    return result


def _plan_layout(paths, settings, progress, analysis, analysis_ready):
    if settings.cutter_mode != "free":
        if settings.cutter_rotation_zone and settings.cutter_mode == "dual":
            from .rotation_zones import plan_rotation_zones
            return plan_rotation_zones(paths, settings, progress, analysis, analysis_ready)
        from .cutter_planner import plan_cutter_layout
        return plan_cutter_layout(paths, settings, progress)
    canvas_width = mm_to_px(settings.media_width_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    usable_width = canvas_width
    if usable_width <= 0:
        raise ValueError("外边距过大，画布没有可打印区域。")
    items, labels = read_items(paths, settings, progress)
    if progress:
        progress('计算排版', 0, len(paths), '开始整批顺序排版计算')
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
    used_width = min(canvas_width, _used_canvas_width(planned))
    return planned, labels, used_width, canvas_height, baseline_height


def _used_canvas_width(planned):
    right_edges = []
    for _path, placement in planned:
        right_edges.append(placement.x_px + placement.width_px)
        if placement.number_width_px:
            right_edges.append(
                placement.number_x_px + placement.number_width_px
            )
        if placement.color_block_width_px:
            right_edges.append(
                placement.color_block_x_px
                + placement.color_block_width_px
            )
    return max(right_edges)


def _baseline_choice(choices, usable_width):
    fitting = next(
        (choice for choice in choices if choice.width <= usable_width),
        None,
    )
    if fitting is None:
        raise ValueError("至少一个图片组超过了材料可打印宽度。")
    return fitting.width, fitting.height


def _place_rows(units, rows, top_margin, spacing):
    planned, y = [], top_margin
    for start, end, choice_indexes in rows:
        row = [
            units[index][choice]
            for index, choice in zip(
                range(start, end), choice_indexes, strict=True
            )
        ]
        row_height = max(choice.height for choice in row)
        x = 0
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
                    base_x + item.block_rx,
                    base_y + item.block_ry,
                    item.block_width,
                    item.block_height,
                ),
            )
        )
    return placed
