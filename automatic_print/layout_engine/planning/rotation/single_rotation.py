"""Linear suffix decisions with a movable whole-size zone boundary."""
from dataclasses import replace

from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.orders.order_groups import complete_orders
from automatic_print.layout_engine.orders.size_policy import single_order_size
from automatic_print.layout_engine.intake.metadata.source_metadata import source_block
from automatic_print.layout_engine.cutting.geometry.transition_marks import marked_height


def eligible_tail(paths, baseline):
    if baseline is None or not all(single_order_size(o) is not None for o in complete_orders(paths)):
        return None  # Mixed/multi-piece batches retain the separate whole-order optimizer.
    rows, sizes, protected = {}, {}, set()
    for path, placement in baseline[0]:
        if placement.rotation_degrees:
            return None  # Manual rotation is not this automatic single-piece policy.
        size = source_block(path)
        sizes.setdefault(size, []).append(path)
        rows.setdefault((placement.row_y_px, placement.y_px), []).append(size)
    for row in rows.values():
        if len(row) > 1:
            protected.update(row)
    tail = []
    for size in reversed(sizes):
        if size in protected:
            break
        tail.append(size)
    if not tail:
        return []
    # A rotation zone already exists after the final protected size. Compare
    # every whole-size suffix so the boundary may move earlier when rotating
    # the adjacent multi-row size block reduces the complete output length.
    return [path for path, _placement in baseline[0]]


def plan_single_rotation(baseline, targets, rotated_items, rotated_labels, settings, progress):
    from .rotation_zones import _rotated, _baseline_result
    width = baseline[2]
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    original_height = marked_height(baseline[0], settings, width, baseline[3])
    if not targets:
        if progress:
            progress('单件旋转筛选', 0, 0, '常规双排尺码块保留；没有可旋转的末尾单排尺码块')
        return _baseline_result(baseline, settings, progress)
    blocks = {}
    for path in targets:
        blocks.setdefault(source_block(path), []).append(path)
    bottoms = {}
    for path, placement in baseline[0]:
        size = source_block(path)
        bottoms[size] = max(bottoms.get(size, 0),
                            placement.row_y_px + placement.footprint_height_px)
    size_order = list(bottoms)
    prefix = {}
    bottom = 0
    for size in size_order:
        prefix[size] = bottom + margin if bottom else 0
        bottom = max(bottom, bottoms[size])
    best, suffix, valid = None, [], True
    ordered_blocks = list(blocks.items())
    for step, (size, paths) in enumerate(reversed(ordered_blocks), 1):
        valid = valid and all(path in rotated_items for path in paths)
        suffix[:0] = paths
        if valid:
            rotated = _rotated(suffix, settings, (rotated_items, rotated_labels))
            normal_height = prefix[size]
            boundary = normal_height + spacing if normal_height else 0
            height = boundary + rotated[2]
            score = height, len(suffix)
            if height < baseline[3] and (best is None or score < best[0]):
                best = score, size, rotated
        if progress:
            progress('单件旋转筛选', step, len(blocks),
                     f'{size}：比较完整尺码后缀，允许向前移动多排区/旋转区分界')
    if best is None:
        return _baseline_result(baseline, settings, progress)
    chosen, enabled = [], False
    for size, paths in blocks.items():
        enabled |= size == best[1]
        if enabled:
            chosen.extend(paths)
    selected = set(chosen)
    normal_knife = mm_to_px(settings.cutter_knife_mm, settings.dpi)
    normal = [(path, replace(placement, cut_zone='常规区', cut_knife_x_px=normal_knife))
              for path, placement in baseline[0] if path not in selected]
    rotated = best[2]
    boundary = prefix[best[1]] + spacing if normal else 0
    planned = normal + [(path, replace(
        placement,
        y_px=placement.y_px + boundary,
        row_y_px=placement.row_y_px + boundary,
        number_y_px=placement.number_y_px + boundary,
        color_block_y_px=placement.color_block_y_px + boundary,
        platform_y_px=placement.platform_y_px + boundary,
        cut_zone='旋转区',
    )) for path, placement in rotated[0]]
    height = marked_height(planned, settings, width, boundary + rotated[2])
    if height >= original_height:
        return _baseline_result(baseline, settings, progress)
    if progress:
        progress('批次刀位已确定', normal_knife if normal else rotated[3], settings.dpi,
                 '同尺码整体锁定；按完整尺码组调整多排区与旋转区分界')
        progress('旋转区节省', original_height - height, settings.dpi,
                 f'旋转区 {len(chosen)} 张；不拆订单、双面或尺码块')
    selected_labels = {
        placement.sequence_number: rotated_labels[placement.sequence_number]
        for _path, placement in rotated[0]
        if placement.sequence_number in rotated_labels
    }
    from automatic_print.layout_engine.planning.columns.cutter_planner import cutter_output_width
    width = cutter_output_width(
        planned, settings, mm_to_px(settings.media_width_mm, settings.dpi),
    )
    return planned, baseline[1] | selected_labels, width, height, original_height
