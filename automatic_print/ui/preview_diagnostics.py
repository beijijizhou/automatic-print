"""Unvalidated placements for visual diagnostics ONLY, never for output."""
from dataclasses import replace
from math import ceil

from ..layout_engine.intake.preparation.item_factory import read_items
from ..layout_engine.domain.models import mm_to_px
from ..layout_engine.planning.base.row_optimizer import _place_choice
from ..layout_engine.planning.packing.units import UnitChoice, UnitMember


def diagnostic_layout(paths, settings, progress=None):
    safe = replace(settings, allow_rotation=False)
    try:
        choices, labels = read_items(paths, safe, progress)
    except ValueError:
        # Even label-recognition failure must not hide the source artwork.
        choices, labels = read_items(paths, replace(safe, number_images=False, platform_name=''), progress)
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    knife = mm_to_px(settings.cutter_knife_mm, settings.dpi)
    safety = ceil(settings.cutter_safety_mm * settings.dpi / 25.4)
    marker = knife + safety + mm_to_px(settings.cutter_marker_offset_mm, settings.dpi)
    planned, overflow, y, row_height = [], [], margin, 0
    for index, options in enumerate(choices):
        item = options[0]
        dual_right = settings.cutter_mode == "dual" and index % 2 == 1
        start = marker if dual_right else 0
        end = knife-safety if settings.cutter_mode == "dual" and not dual_right else width
        x = start-item.block_rx if item.block_width else start
        row = UnitChoice(x+item.footprint_width, item.footprint_height,
                         (UnitMember(item, x, 0),), 0)
        planned.extend(_place_choice(row, 0, y))
        row_height = max(row_height, item.footprint_height)
        if x+item.footprint_width > end:
            overflow.append((end, y, x+item.footprint_width-end, item.footprint_height))
        if settings.cutter_mode != "dual" or dual_right:
            y += row_height+spacing
            row_height = 0
    height = max(p.row_y_px+p.footprint_height_px for _, p in planned)+margin
    return planned, labels, height, overflow
