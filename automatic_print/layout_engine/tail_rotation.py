"""Bounded suffix comparisons for known single-piece size blocks, not all-batch DP."""
from dataclasses import replace

from .cutter_planner import plan_cutter_layout
from .models import mm_to_px
from .order_groups import complete_orders, ordered_paths
from .size_policy import single_order_size
from .source_metadata import source_size, size_key
from .transition_marks import marked_height


def plan_tail_rotation(paths, settings, progress):
    from .rotation_zones import rotation_items, _rotated
    effective = [settings]
    def report(stage, current, total, filename):
        if stage == '批次刀位已确定':
            effective[0] = replace(settings, cutter_knife_mm=current*25.4/total)
        if progress:
            progress(stage, current, total, filename)
    baseline = plan_cutter_layout(paths, settings, report)
    orders = complete_orders(paths)
    if not all(single_order_size(order) is not None for order in orders):
        return baseline
    ordered = ordered_paths(paths)
    sizes = sorted({source_size(p) for p in ordered if 80 <= size_key(source_size(p))[0] < 1000}, key=size_key)
    if not sizes:
        return baseline
    selected = [p for p in ordered if source_size(p) in sizes]
    options, labels = rotation_items(selected, settings)
    width = baseline[2]
    original_height = marked_height(baseline[0], settings, width, baseline[3])
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    normal_knife = mm_to_px(effective[0].cutter_knife_mm, settings.dpi)
    best = None
    for index, first_size in enumerate(sizes):
        if progress:
            progress('比较末尾旋转', index, len(sizes), f'比较 {first_size} 及之后的完整尺码块')
        targets = [p for p in selected if size_key(source_size(p)) >= size_key(first_size)]
        rotated = _rotated(targets, settings, (options, labels))
        if rotated is None:
            continue
        target_set = set(targets)
        normal = [(path, replace(p, cut_zone='常规区', cut_knife_x_px=normal_knife))
                  for path, p in baseline[0] if path not in target_set]
        boundary = max(p.row_y_px+p.footprint_height_px for _, p in normal)+margin+spacing if normal else 0
        planned = normal+[(path, replace(p, y_px=p.y_px+boundary, row_y_px=p.row_y_px+boundary,
                            number_y_px=p.number_y_px+boundary, color_block_y_px=p.color_block_y_px+boundary,
                            platform_y_px=p.platform_y_px+boundary,
                            cut_zone='旋转区', cut_knife_x_px=rotated[3])) for path, p in rotated[0]]
        height = marked_height(planned, settings, width, boundary+rotated[2])
        score = height, len(targets)
        if height < original_height and (best is None or score < best[0]):
            best = score, planned, baseline[1] | labels
    if progress:
        progress('比较末尾旋转', len(sizes), len(sizes),
                 '已计入红线、区域间距和批次留白；只有整批更省膜才启用')
    if best is None:
        return baseline
    # Keep the normal knife reported by the original fast batch search.
    return best[1], best[2], width, best[0][0], original_height
