"""Linear contiguous knife zones: isolate width outliers without reordering."""
from dataclasses import replace

from .cutter_planner import (
    _horizontal, _lanes, cutter_output_width, plan_cutter_layout,
    read_cutter_items,
)
from .models import mm_to_px
from .order_groups import complete_orders, ordered_paths
from .single_order_sequence import lane_fits


def plan_adaptive_knife_zones(paths, settings, progress):
    """Use balanced zones for pairable runs and separate knives for outliers."""
    if settings.cutter_mode != 'dual' or not settings.cutter_auto_knife:
        return plan_cutter_layout(paths, settings, progress)
    base = replace(settings, cutter_rotation_zone=False, cutter_tail_rotation=False,
                   allow_rotation=False, manual_rotations=())
    paths = ordered_paths(paths)
    options, labels = read_cutter_items(paths, base, progress)
    items = {row[0].path: row[0] for row in options}
    lanes = _lanes(replace(base, cutter_auto_knife=False,
                           cutter_knife_mm=base.media_width_mm/2),
                   mm_to_px(base.media_width_mm, base.dpi))
    runs = _contiguous_runs(complete_orders(paths), items, lanes)
    if len(runs) == 1:
        return plan_cutter_layout(paths, base, progress, prepared=(options, labels),
                                  preserve_sequence=True)
    planned, height, zone_index = [], 0, 0
    for balanced, orders in runs:
        selected = [path for order in orders for path in order]
        effective = [base]

        def report(stage, current, total, filename):
            if stage == '批次刀位已确定':
                effective[0] = replace(base, cutter_knife_mm=current*25.4/total)
            if progress:
                progress('连续刀位分区：'+stage, current, total, filename)

        prepared = ([[items[path]] for path in selected], labels)
        result = plan_cutter_layout(selected, base, report, prepared=prepared,
                                    preserve_sequence=True)
        knife = mm_to_px(effective[0].cutter_knife_mm, base.dpi)
        zone_index += 1
        zone = ('双排区' if balanced else '宽图区')+str(zone_index)
        shifted = [_shift(path, placement, height, zone, knife)
                   for path, placement in result[0]]
        planned.extend(shifted)
        height += result[3]+mm_to_px(base.spacing_mm, base.dpi)
    height -= mm_to_px(base.spacing_mm, base.dpi)
    maximum = mm_to_px(base.media_width_mm, base.dpi)
    width = cutter_output_width(planned, base, maximum)
    if progress:
        progress('连续刀位分区', len(runs), len(runs),
                 f'{len(runs)}个连续区域；保持订单顺序，宽图不再拖累可双排区域')
    return planned, labels, width, height, height


def _contiguous_runs(orders, items, lanes):
    runs = []
    for order in orders:
        balanced = _balanced(order, items, lanes)
        if not runs or runs[-1][0] != balanced:
            runs.append((balanced, []))
        runs[-1][1].append(order)
    return runs


def _balanced(order, items, lanes):
    members = [items[path] for path in order]
    if len(members) == 1:
        return all(lane_fits(members[0], lane) for lane in lanes)
    if len(members) == 2:
        return _horizontal(members, lanes) is not None
    return False


def _shift(path, placement, offset, zone, knife):
    return path, replace(
        placement, y_px=placement.y_px+offset,
        row_y_px=placement.row_y_px+offset,
        number_y_px=placement.number_y_px+offset,
        color_block_y_px=placement.color_block_y_px+offset,
        platform_y_px=placement.platform_y_px+offset,
        cut_zone=zone, cut_knife_x_px=knife,
    )
