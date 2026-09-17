"""Choose the number of cutter columns; column count is a result, not a mode."""
from dataclasses import replace
from math import ceil

from automatic_print.layout_engine.domain.models import mm_to_px


MAX_COLUMNS = 8


def equal_knives(width, columns):
    return tuple(round(width * index / columns) for index in range(1, columns))


def lanes_for_knives(settings, width, knives):
    safety = ceil(settings.cutter_safety_mm * settings.dpi / 25.4)
    offset = mm_to_px(settings.cutter_marker_offset_mm, settings.dpi)
    knives = tuple(sorted(knives))
    boundaries = (0,) + knives + (width,)
    lanes = []
    for index in range(len(boundaries) - 1):
        start = boundaries[index] + (safety if index else 0)
        end = boundaries[index + 1] - (safety if index < len(knives) else 0)
        marker = None if index == 0 else boundaries[index] + safety + offset
        if start >= end or marker is not None and marker >= end:
            raise ValueError('刀位和安全区超出了膜宽，无法形成有效分栏。')
        lanes.append((start, end, marker))
    return lanes


def select_columns(groups, settings, spacing, progress=None):
    """Compare safe equal-width 1..N column plans and return the shortest."""
    from .cutter_planner import solve_groups
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    maximum = min(MAX_COLUMNS, max(1, len(groups),
                                   max(map(len, groups), default=1)))
    candidates = []
    # Two columns may need an asymmetric knife (for example a wide image on the
    # left and a small companion on the right). Preserve that exact optimizer.
    if maximum >= 2:
        try:
            from .knife_optimizer import select_batch_knife
            from .cutter_planner import _lanes
            asymmetric = select_batch_knife(groups, settings, spacing)
            lanes = _lanes(asymmetric, width)
            result = solve_groups(groups, lanes, spacing,
                                  settings.cutter_majority_two_zone)
            if result is not None:
                knife = mm_to_px(asymmetric.cutter_knife_mm, settings.dpi)
                used = _used_columns(result)
                candidates.append((result[0], -used, 1, (knife,) if used > 1 else (), lanes))
        except ValueError:
            pass
    for columns in [1, *range(3, maximum + 1)]:
        knives = equal_knives(width, columns)
        try:
            lanes = lanes_for_knives(settings, width, knives)
            result = (solve_groups(groups, lanes, spacing,
                                   settings.cutter_majority_two_zone)
                      if columns == 1 or _can_fill_columns(groups, lanes)
                      else None)
        except ValueError:
            result = None
        if result is not None:
            used = _used_columns(result)
            candidates.append((result[0], -used, len(knives),
                               knives if used > 1 else (), lanes))
        if progress:
            progress('计算自动分栏', columns, maximum,
                     f'比较 {columns} 列及 {max(0, columns-1)} 个固定刀位')
    if not candidates:
        raise ValueError('当前膜宽不存在安全的自动分栏方案。')
    _height, _negative_columns, _knife_count, knives, lanes = min(candidates)
    selected = replace(settings,
                       cutter_knife_mm=(knives[0] * 25.4 / settings.dpi
                                        if knives else settings.cutter_knife_mm))
    return selected, lanes, knives


def _can_fill_columns(groups, lanes):
    """Reject N-column candidates unless N distinct items can fill all lanes."""
    from .column_solver import member

    full = (1 << len(lanes)) - 1
    reachable = {0}
    for item in (item for group in groups for item in group):
        fitting = 0
        for lane_index, lane in enumerate(lanes):
            if member(item, lane) is not None:
                fitting |= 1 << lane_index
        if not fitting:
            return False
        expanded = set(reachable)
        for used in reachable:
            available = fitting & ~used
            while available:
                bit = available & -available
                expanded.add(used | bit)
                available ^= bit
        reachable = expanded
    return full in reachable


def _used_columns(solution):
    return max((len({member.x for member in row.members})
                for _count, row in solution[1]), default=1)
