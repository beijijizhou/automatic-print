"""Ordered, unrotated layouts constrained by one batch-wide knife position."""
from dataclasses import replace
from math import ceil

from .images import print_dimensions
from .order_groups import ordered_paths, order_key
from .item_factory import read_items
from .models import mm_to_px
from .units import UnitChoice, UnitMember, build_units
from .single_order_sequence import arrange_groups
from .size_policy import same_single_size
from .measurement_session import resolved_name


def plan_cutter_layout(paths, settings, progress, prepared=None, preserve_sequence=False):
    from .planner import _place_choice, _used_canvas_width

    settings = replace(settings, sequence_numbers=settings.sequence_numbers or
                       tuple((resolved_name(path), i) for i, path in enumerate(paths, 1)))
    paths = ordered_paths(paths)
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    items, labels = prepared if prepared is not None else read_cutter_items(paths, settings, progress)
    if progress:
        progress('计算排版', 0, len(paths), '整理完整订单与固定分区占位')
    units = build_units(items, spacing)
    groups = [[member.item for member in choices[0].members] for choices in units]
    if settings.cutter_mode == "dual" and settings.cutter_auto_knife:
        from .knife_optimizer import select_batch_knife
        settings = select_batch_knife(groups, settings, spacing, progress)
    lanes = _lanes(settings, width)
    if not preserve_sequence:
        groups = arrange_groups(groups, lanes, settings)
    if progress:
        progress("批次刀位已确定", mm_to_px(settings.cutter_knife_mm, settings.dpi),
                 settings.dpi, f"整批固定刀位 {settings.cutter_knife_mm:.2f} 毫米")
    solution = solve_groups(groups, lanes, spacing)
    if solution is None:
        raise ValueError("图片无法安全放入固定分区；单排必须靠左，请启用自动刀位、增大左分区或改用单列。")
    _, plans = solution
    planned, index, y = [], 0, margin
    while index < len(groups):
        count, row = plans[index]
        planned.extend(_place_choice(row, 0, y))
        y += row.height + spacing
        index += count
    height = y - spacing + margin
    independent = [min((row.height for row in _group_rows(group, lanes, spacing)),
                       default=None) for group in groups]
    # A wide item may safely pair on the right but cannot stand alone on the left.
    # No independent baseline exists then; never crash or invent a saving.
    baseline = (sum(h+spacing for h in independent)-spacing+2*margin
                if all(h is not None for h in independent) else height)
    if progress:
        progress("切膜安全检查", len(paths), len(paths), "刀位及左右色块基准整批固定")
    output_width = width if settings.cutter_mode == "dual" else min(width, _used_canvas_width(planned))
    return planned, labels, output_width, height, baseline


def solve_groups(groups, lanes, spacing):
    from collections import Counter
    counts = Counter(order_key(item.path) for group in groups for item in group)
    costs, plans = [float("inf")] * (len(groups) + 1), [None] * len(groups)
    costs[-1] = 0
    for index in range(len(groups) - 1, -1, -1):
        candidates = [(1, row) for row in _group_rows(groups[index], lanes, spacing)]
        if len(lanes) == 2 and index + 1 < len(groups):
            if len(groups[index]) == len(groups[index + 1]) == 1:
                pair = groups[index] + groups[index + 1]
                keys = [order_key(item.path) for item in pair]
                share = keys[0] == keys[1] or (all(counts[key] == 1 for key in keys)
                                             and same_single_size(pair[0].path, pair[1].path))
                row = _horizontal(pair, lanes) if share else None
                if row:
                    candidates.insert(0, (2, row))
        for count, row in candidates:
            cost = row.height + spacing + costs[index + count]
            if cost < costs[index]:
                costs[index], plans[index] = cost, (count, row)
        if plans[index] is None:
            return None
    return costs[0], plans


def _lanes(settings, width):
    if settings.cutter_mode == "single":
        return [(0, width, None)]
    knife = mm_to_px(settings.cutter_knife_mm, settings.dpi)
    safety = ceil(settings.cutter_safety_mm * settings.dpi / 25.4)
    offset = mm_to_px(settings.cutter_marker_offset_mm, settings.dpi)
    if not 0 < knife - safety < knife + safety < width:
        raise ValueError("刀位和安全区必须位于膜宽范围内，且左右分区都必须有可用空间。")
    marker = knife + safety + offset
    if marker >= width:
        raise ValueError("右侧色块基准超出了膜宽。")
    return [(0, knife - safety, None), (knife + safety, width, marker)]


def _member(item, lane, y=0):
    start, end, marker = lane
    x = start if marker is None else marker - item.block_rx
    if x < start or x + item.footprint_width > end:
        return None
    return UnitMember(item, x, y)


def _row(members):
    return UnitChoice(
        max(m.x + m.item.footprint_width for m in members),
        max(m.y + m.item.footprint_height for m in members),
        tuple(members), 0,
    )


def _horizontal(group, lanes):
    if len(lanes) != 2 or any(item.rotation_degrees for item in group):
        return None
    members = [_member(item, lane) for item, lane in zip(group, lanes)]
    if any(member is None for member in members):
        members = [_member(item, lane) for item, lane in zip(group, reversed(lanes))]
        if any(member is None for member in members):
            return None
    anchor_y = max(member.item.image_ry for member in members)
    return _row([
        replace(member, y=anchor_y - member.item.image_ry)
        for member in members
    ])


def _group_rows(group, lanes, spacing):
    rows = []
    if len(group) == 2:
        horizontal = _horizontal(group, lanes)
        if horizontal:
            return [horizontal]
    # A vertical/single-image row must be readable by the film's left sensor.
    # Right-lane placement is only valid with an actual horizontal companion.
    for lane in lanes[:1]:
        members, y = [], 0
        for item in group:
            member = _member(item, lane, y)
            if member is None:
                break
            members.append(member)
            y += item.footprint_height + spacing
        if len(members) == len(group):
            rows.append(_row(members))
    return rows


def read_cutter_items(paths, settings, progress):
    if settings.cutter_mode not in {"single", "dual"}:
        raise ValueError("未知的切膜排版模式。")
    if not settings.color_block_enabled:
        raise ValueError("切膜模式必须启用左侧识别色块。")
    safe_settings = replace(
        settings, allow_rotation=False, color_block_position="left_top",
        color_block_offset_y_mm=0,
    )
    if progress:
        progress('读取图片尺寸', 0, len(paths), '读取内嵌 DPI、尺寸和标签占位')
    dimensions = [print_dimensions(path, settings.dpi) for path in paths]
    missing = [path.name for path, size in zip(paths, dimensions) if not size.embedded_dpi]
    if missing:
        raise ValueError(
            "以下图片没有可靠的内嵌 DPI，无法确认打印尺寸；请先补充图片 DPI：\n"
            + "\n".join(missing[:20])
        )
    return read_items(paths, safe_settings, progress)
