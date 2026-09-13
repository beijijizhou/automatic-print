"""Ordered, unrotated layouts constrained by one batch-wide knife position."""
from dataclasses import replace
from math import ceil

from .images import print_dimensions
from .item_factory import read_items
from .models import mm_to_px
from .units import UnitChoice, UnitMember, build_units


def plan_cutter_layout(paths, settings, progress):
    from .planner import _place_choice, _used_canvas_width

    width = mm_to_px(settings.media_width_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    if settings.cutter_mode not in {"single", "dual"}:
        raise ValueError("未知的切膜排版模式。")
    if not settings.color_block_enabled:
        raise ValueError("切膜模式必须启用左侧识别色块。")
    safe_settings = replace(
        settings, allow_rotation=False, color_block_position="left_top",
        color_block_offset_y_mm=0,
    )
    dimensions = [print_dimensions(path, settings.dpi) for path in paths]
    missing = [path.name for path, size in zip(paths, dimensions) if not size.embedded_dpi]
    if missing:
        raise ValueError(
            "以下图片没有可靠的内嵌 DPI，无法确认打印尺寸；请先补充图片 DPI：\n"
            + "\n".join(missing[:20])
        )
    items, labels = read_items(paths, safe_settings, progress)
    units = build_units(items, spacing)
    groups = [[member.item for member in choices[0].members] for choices in units]
    lanes = _lanes(settings, width)
    costs, plans = [float("inf")] * (len(groups) + 1), [None] * len(groups)
    costs[-1] = 0
    for index in range(len(groups) - 1, -1, -1):
        candidates = [(1, row) for row in _group_rows(groups[index], lanes, spacing)]
        if settings.cutter_mode == "dual" and index + 1 < len(groups):
            if len(groups[index]) == len(groups[index + 1]) == 1:
                row = _horizontal(groups[index] + groups[index + 1], lanes)
                if row:
                    candidates.append((2, row))
        for count, row in candidates:
            cost = row.height + spacing + costs[index + count]
            if cost < costs[index]:
                costs[index], plans[index] = cost, (count, row)
        if plans[index] is None:
            item = groups[index][0]
            raise ValueError(
                f"{item.path.name} 无法安全放入固定分区。图片打印尺寸 "
                f"{item.width * 25.4 / settings.dpi:.1f} × "
                f"{item.height * 25.4 / settings.dpi:.1f} 毫米；"
                "分区检查同时包含标签、色块和安全区，请调整刀位或膜规格。"
            )
    planned, index, y = [], 0, margin
    while index < len(groups):
        count, row = plans[index]
        planned.extend(_place_choice(row, 0, y))
        y += row.height + spacing
        index += count
    height = y - spacing + margin
    baseline = sum(
        min(row.height for row in _group_rows(group, lanes, spacing)) + spacing
        for group in groups
    ) - spacing + 2 * margin
    if progress:
        progress("切膜安全检查", len(paths), len(paths), "方向不变，刀位及右侧色块基准整批固定")
    return planned, labels, min(width, _used_canvas_width(planned)), height, baseline


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
    if len(lanes) != 2:
        return None
    members = [_member(item, lane) for item, lane in zip(group, lanes)]
    if any(member is None for member in members):
        return None
    anchor_y = max(member.item.block_ry for member in members)
    return _row([
        replace(member, y=anchor_y - member.item.block_ry)
        for member in members
    ])


def _group_rows(group, lanes, spacing):
    rows = []
    if len(group) == 2:
        horizontal = _horizontal(group, lanes)
        if horizontal:
            rows.append(horizontal)
    for lane in lanes:
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
