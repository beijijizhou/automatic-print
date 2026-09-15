"""Two production zones: majority double rows, then rotated leftovers."""
from dataclasses import replace

from .cutter_planner import (
    _horizontal, _lanes, cutter_output_width, plan_cutter_layout,
    read_cutter_items,
)
from .models import mm_to_px
from .order_groups import complete_orders, ordered_paths
from .single_order_sequence import lane_fits


def plan_adaptive_knife_zones(paths, settings, progress):
    """Keep the pairable majority together and rotate complete leftovers."""
    if settings.cutter_mode != 'dual' or not settings.cutter_auto_knife:
        raise ValueError('多数双排分区只适用于自动双刀模式。')
    base = replace(settings, cutter_rotation_zone=False, cutter_tail_rotation=False,
                   allow_rotation=False)
    paths = ordered_paths(paths)
    options, labels = read_cutter_items(paths, base, progress)
    items = {row[0].path: row[0] for row in options}
    lanes = _lanes(replace(base, cutter_auto_knife=False,
                           cutter_knife_mm=base.media_width_mm/2),
                   mm_to_px(base.media_width_mm, base.dpi))
    double_orders, leftovers = _partition(complete_orders(paths), items, lanes)
    normal_paths = [path for order in double_orders for path in order]
    rotated_paths = [path for order in leftovers for path in order]
    if len(normal_paths) <= len(rotated_paths):
        raise ValueError('可安全双排的图片未超过半数，改用常规旋转方案比较。')

    effective = [base]
    def report(stage, current, total, filename):
        if stage == '批次刀位已确定':
            effective[0] = replace(base, cutter_knife_mm=current*25.4/total)
        if progress:
            progress('双排区：'+stage, current, total, filename)
    normal = plan_cutter_layout(
        normal_paths, base, report,
        prepared=([[items[path]] for path in normal_paths], labels),
        preserve_sequence=True,
    )

    if not rotated_paths:
        knife = mm_to_px(effective[0].cutter_knife_mm, base.dpi)
        planned = [(path, replace(p, cut_zone='双排区', cut_knife_x_px=knife))
                   for path, p in normal[0]]
        if progress:
            progress('双排与旋转分区', len(paths), len(paths),
                     f'全部{len(paths)}张进入双排区；没有剩余旋转区；共1个区域')
        return planned, normal[1], normal[2], normal[3], normal[4]

    from .rotation_zones import _rotated, rotation_items
    rotated_items, rotated_labels = rotation_items(rotated_paths, base, progress)
    missing = [path.name for path in rotated_paths if path not in rotated_items]
    if missing:
        raise ValueError('剩余图片旋转后仍超宽，需要进入等比缩小恢复：'+'、'.join(missing))
    rotated = _rotated(rotated_paths, base, (rotated_items, rotated_labels))
    spacing = mm_to_px(base.spacing_mm, base.dpi)
    boundary = normal[3]+spacing
    normal_knife = mm_to_px(effective[0].cutter_knife_mm, base.dpi)
    planned = [(path, replace(p, cut_zone='双排区', cut_knife_x_px=normal_knife))
               for path, p in normal[0]]
    planned.extend(_shift(path, placement, boundary, rotated[3])
                   for path, placement in rotated[0])
    height = boundary+rotated[2]
    width = cutter_output_width(
        planned, base, mm_to_px(base.media_width_mm, base.dpi)
    )
    if progress:
        progress('双排与旋转分区', len(paths), len(paths),
                 f'双排区{len(normal_paths)}张；旋转区{len(rotated_paths)}张；共2个区域')
    return planned, labels | rotated_labels, width, height, height


def _partition(orders, items, lanes):
    double, leftovers = [], []
    for order in orders:
        (double if _pairable(order, items, lanes) else leftovers).append(order)
    return double, leftovers


def _pairable(order, items, lanes):
    from .source_metadata import source_size
    if any(source_size(path) in {'3XL', '4XL', '5XL'} for path in order):
        return False
    members = [items[path] for path in order]
    if any(item.rotation_degrees for item in members):
        return False
    if len(members) == 1:
        return all(lane_fits(members[0], lane) for lane in lanes)
    if len(members) == 2:
        return _horizontal(members, lanes) is not None
    return False


def _shift(path, placement, offset, knife):
    return path, replace(
        placement, y_px=placement.y_px+offset,
        row_y_px=placement.row_y_px+offset,
        number_y_px=placement.number_y_px+offset,
        color_block_y_px=placement.color_block_y_px+offset,
        platform_y_px=placement.platform_y_px+offset,
        cut_zone='旋转区', cut_knife_x_px=knife,
    )
