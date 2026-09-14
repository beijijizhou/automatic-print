"""Linear suffix decisions: preserve double rows, rotate only unpaired size tails."""
from dataclasses import replace

from .models import mm_to_px
from .order_groups import complete_orders
from .size_policy import single_order_size
from .source_metadata import source_block
from .transition_marks import marked_height


def eligible_tail(paths, baseline):
    if baseline is None or not all(single_order_size(o) is not None for o in complete_orders(paths)):
        return None  # Mixed/multi-piece batches retain the separate whole-order optimizer.
    rows, sizes, protected = {}, {}, set()
    for path, p in baseline[0]:
        if p.rotation_degrees:
            return None  # Manual rotation is not this automatic single-piece policy.
        size = source_block(path)
        sizes.setdefault(size, []).append(path)
        rows.setdefault((p.row_y_px, p.y_px), []).append(size)
    for row in rows.values():
        if len(row) > 1:
            protected.update(row)
    tail = []
    for size in reversed(sizes):
        if size in protected:
            break  # Keep complete size blocks and ascending normal -> rotated production.
        tail.append(size)
    allowed = set(tail)
    return [path for path, _ in baseline[0] if source_block(path) in allowed]


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
    for path, p in baseline[0]:
        bottoms[source_block(path)] = max(bottoms.get(source_block(path), 0),
                                        p.row_y_px+p.footprint_height_px)
    size_order = list(bottoms)
    prefix = {}
    bottom = 0
    for size in size_order:
        prefix[size] = bottom+margin if bottom else 0
        bottom = max(bottom, bottoms[size])
    best, accumulated, count, valid = None, 0, 0, True
    for step, (size, paths) in enumerate(reversed(list(blocks.items())), 1):
        valid = valid and all(path in rotated_items for path in paths)
        count += len(paths)
        if valid:
            accumulated += sum(rotated_items[path].footprint_height+spacing for path in paths)
            normal_height = prefix[size]
            boundary = normal_height+spacing if normal_height else 0
            height = boundary+accumulated-spacing+2*margin
            score = height, count
            if height < baseline[3] and (best is None or score < best[0]):
                best = score, size
        if progress:
            progress('单件旋转筛选', step, len(blocks), f'{size}：只比较完整单排尺码后缀，不搜索旋转刀位组合')
    if best is None:
        return _baseline_result(baseline, settings, progress)
    chosen, enabled = [], False
    for size, paths in blocks.items():
        enabled |= size == best[1]
        if enabled:
            chosen.extend(paths)
    selected = set(chosen)
    normal_knife = mm_to_px(settings.cutter_knife_mm, settings.dpi)
    normal = [(path, replace(p, cut_zone='常规区', cut_knife_x_px=normal_knife))
              for path, p in baseline[0] if path not in selected]
    rotated = _rotated(chosen, settings, (rotated_items, rotated_labels))
    boundary = prefix[best[1]]+spacing if normal else 0
    planned = normal+[(path, replace(p, y_px=p.y_px+boundary, row_y_px=p.row_y_px+boundary,
        number_y_px=p.number_y_px+boundary, color_block_y_px=p.color_block_y_px+boundary,
        platform_y_px=p.platform_y_px+boundary, cut_zone='旋转区', cut_knife_x_px=rotated[3]))
        for path, p in rotated[0]]
    height = marked_height(planned, settings, width, boundary+rotated[2])
    if height >= original_height:
        return _baseline_result(baseline, settings, progress)
    if progress:
        progress('批次刀位已确定', normal_knife if normal else rotated[3], settings.dpi,
                 '单件双排优先；仅完整末尾单排尺码块旋转')
        progress('旋转区节省', original_height-height, settings.dpi,
                 f'旋转区 {len(chosen)} 张；保留双排，不拆订单、双面或尺码块')
    selected_labels = {p.sequence_number: rotated_labels[p.sequence_number] for _, p in rotated[0]
                       if p.sequence_number in rotated_labels}
    return planned, baseline[1] | selected_labels, width, height, original_height
