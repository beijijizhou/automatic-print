"""One fixed cutter position with per-unit normal/rotated choices."""
from dataclasses import replace

from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.orders.single_order_sequence import (
    arrange_groups, arrange_groups_within_orders,
)
from automatic_print.layout_engine.planning.base.row_optimizer import _place_choice
from automatic_print.layout_engine.planning.packing.units import build_units

from .column_solver import solve_group_choices
from .cutter_planner import _lanes, cutter_output_width
from .knife_optimizer import knife_candidates


def riin_sequence_height(items, width, spacing, margin=0):
    """Next-fit shelf baseline in the untouched input sequence."""
    height = row_height = used = 0
    for item in items:
        needed = item.footprint_width + (spacing if used else 0)
        if used and used + needed > width:
            height += row_height + spacing
            used = row_height = 0
        used += item.footprint_width + (spacing if used else 0)
        row_height = max(row_height, item.footprint_height)
    return height + row_height + 2 * margin


def plan_choice_cutter_layout(
    paths, settings, options, labels, spacing, preserve_sequence=False,
):
    """Choose orientation per unit without moving the zone's vertical knife."""
    units = build_units(options, spacing)
    choice_groups = [_unit_groups(choices) for choices in units]
    representatives = [choices[0] for choices in choice_groups]
    by_paths = {
        tuple(item.path for item in choices[0]): choices
        for choices in choice_groups
    }
    all_groups = [group for choices in choice_groups for group in choices]
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    best = None
    for knife in knife_candidates(all_groups, settings):
        trial = replace(settings, cutter_knife_mm=knife*25.4/settings.dpi)
        lanes = _lanes(trial, width)
        ordered = (
            representatives if preserve_sequence else
            arrange_groups_within_orders(
                arrange_groups(representatives, lanes, trial), lanes,
            )
        )
        ordered_choices = [by_paths[tuple(item.path for item in group)]
                           for group in ordered]
        result = solve_group_choices(
            ordered_choices, lanes, spacing, pair_adjacent=True,
            allow_order_boundary=True,
            # RIIN's control candidate may fill a row with any adjacent single
            # images. Optimized production candidates still obey the existing
            # colour and complete-order boundaries.
            allow_any_adjacent=preserve_sequence,
        )
        if result is not None:
            score = result[0], abs(knife-width/2), knife
            if best is None or score < best[0]:
                best = score, result, knife, ordered_choices
    if best is None:
        raise ValueError('第二分区的原方向与旋转方向均无法形成统一安全刀位。')
    _score, (_height, plans), knife, choice_groups = best
    from automatic_print.layout_engine.labeling.markers.left_marker import head_margin
    margin = head_margin(settings)
    planned, index, y = [], 0, margin
    while index < len(choice_groups):
        count, row = plans[index]
        planned.extend((path, replace(
            placement, cut_knife_x_px=knife,
            cut_knife_xs_px=(knife,), cut_column_count=2,
            cut_zone='旋转区',
        )) for path, placement in _place_choice(row, 0, y))
        y += row.height + spacing
        index += count
    height = max(0, y-spacing+margin)
    output_width = cutter_output_width(planned, settings, width)
    return planned, labels, output_width, height, height


def _unit_groups(choices):
    groups = {}
    for choice in choices:
        members = tuple(member.item for member in choice.members)
        rotations = {item.rotation_degrees for item in members}
        if len(rotations) != 1:
            continue
        key = tuple((item.path, item.rotation_degrees) for item in members)
        groups.setdefault(key, list(members))
    return list(groups.values())
