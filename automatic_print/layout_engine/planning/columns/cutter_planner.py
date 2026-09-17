"""Ordered, unrotated layouts constrained by one batch-wide knife position."""
from dataclasses import replace
from math import ceil

from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.orders.order_groups import ordered_paths
from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.planning.packing.units import build_units
from automatic_print.layout_engine.orders.single_order_sequence import arrange_groups
from automatic_print.layout_engine.measurement.measurement_session import resolved_name
from automatic_print.layout_engine.planning.columns.column_solver import solve_groups, horizontal as _horizontal, group_rows as _group_rows


def plan_cutter_layout(paths, settings, progress, prepared=None, preserve_sequence=False):
    from automatic_print.layout_engine.planning.base.planner import _place_choice, _used_canvas_width

    settings = replace(settings, sequence_numbers=settings.sequence_numbers or
                       tuple((resolved_name(path), i) for i, path in enumerate(paths, 1)))
    paths = ordered_paths(paths)
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    from automatic_print.layout_engine.labeling.markers.left_marker import head_margin
    margin = head_margin(settings)
    items, labels = prepared if prepared is not None else read_cutter_items(paths, settings, progress)
    if progress:
        progress('计算排版', 0, len(paths), '整理完整订单与固定分区占位')
    units = build_units(items, spacing)
    groups = [[member.item for member in choices[0].members] for choices in units]
    knives = ()
    if settings.cutter_mode == "dual" and settings.cutter_auto_knife:
        from .dynamic_columns import select_columns
        settings, lanes, knives = select_columns(groups, settings, spacing, progress)
    else:
        lanes = _lanes(settings, width)
        if settings.cutter_mode == 'dual':
            knives = (mm_to_px(settings.cutter_knife_mm, settings.dpi),)
    if not preserve_sequence:
        groups = arrange_groups(groups, lanes, settings)
    if progress:
        knife_text = '、'.join(f'{knife*25.4/settings.dpi:.2f}' for knife in knives)
        progress("批次刀位已确定", knives[0] if knives else 0,
                 settings.dpi, f"自动 {len(lanes)} 列；固定刀位 {knife_text or '无'} 毫米")
    solution = solve_groups(groups, lanes, spacing, settings.cutter_majority_two_zone)
    if solution is None:
        from automatic_print.layout_engine.diagnostics.error_parameters import groups_failure
        raise ValueError("图片无法安全放入固定分区；单排必须靠左，请启用自动刀位、增大左分区或改用单列。\n"+groups_failure(groups,settings))
    _, plans = solution
    planned, index, y = [], 0, margin
    while index < len(groups):
        count, row = plans[index]
        planned.extend((path, replace(placement,
                                     cut_knife_x_px=knives[0] if knives else None,
                                     cut_knife_xs_px=knives,
                                     cut_column_count=len(lanes)))
                       for path, placement in _place_choice(row, 0, y))
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
    output_width = cutter_output_width(planned, settings, width)
    return planned, labels, output_width, height, baseline


def cutter_output_width(planned, settings, maximum):
    """Trim unused right canvas while retaining every active knife corridor."""
    from automatic_print.layout_engine.planning.base.planner import _used_canvas_width
    used = _used_canvas_width(planned)
    if settings.cutter_mode != 'dual':
        return min(maximum, used)
    safety = ceil(settings.cutter_safety_mm*settings.dpi/25.4)
    knives = [knife for _path, p in planned for knife in p.cut_knife_xs_px]
    if not knives and any(p.cut_column_count == 1 for _path, p in planned):
        return min(maximum, used)
    if not knives:
        knives = [p.cut_knife_x_px for _path, p in planned if p.cut_knife_x_px is not None]
    if not knives:
        knives = [mm_to_px(settings.cutter_knife_mm, settings.dpi)]
    return min(maximum, max(used, max(knives)+safety+1))


def _lanes(settings, width):
    if settings.cutter_mode == "single":
        return [(0, width, None)]
    knife = mm_to_px(settings.cutter_knife_mm, settings.dpi)
    safety = ceil(settings.cutter_safety_mm * settings.dpi / 25.4)
    offset = mm_to_px(settings.cutter_marker_offset_mm, settings.dpi)
    if safety < 0 or knife - safety <= 0 or knife + safety >= width:
        raise ValueError("刀位和安全区必须位于膜宽范围内，且左右分区都必须有可用空间。")
    marker = knife + safety + offset
    if marker >= width:
        raise ValueError("右侧色块基准超出了膜宽。")
    return [(0, knife - safety, None), (knife + safety, width, marker)]


def read_cutter_items(paths, settings, progress, prepare_rotations=False, include_choices=False):
    if settings.cutter_mode not in {"single", "dual"}:
        raise ValueError("未知的切膜排版模式。")
    if not settings.color_block_enabled:
        raise ValueError("切膜模式必须启用左侧识别色块。")
    safe_settings = replace(
        settings, allow_rotation=bool(prepare_rotations or settings.compare_film_sizes
                                      or settings.cutter_compare_whole_rotation), color_block_position="left_top",
        color_block_offset_y_mm=0,
    )
    from automatic_print.layout_engine.measurement.cutter_measurements import load_cutter_measurements, store_cutter_measurements
    cached = load_cutter_measurements(paths, safe_settings)
    if cached is not None:
        items, labels = cached
        return (items if include_choices else [[choices[0]] for choices in items]), labels
    if progress:
        progress('读取图片尺寸', 0, len(paths), '读取内嵌 DPI、尺寸和标签占位')
    dimensions = [print_dimensions(path, settings.dpi) for path in paths]
    missing = [path.name for path, size in zip(paths, dimensions) if not size.embedded_dpi]
    if missing:
        raise ValueError(
            "以下图片没有可靠的内嵌 DPI，无法确认打印尺寸；请先补充图片 DPI：\n"
            + "\n".join(missing[:20])
        )
    items, labels = read_items(paths, safe_settings, progress)
    store_cutter_measurements(paths, safe_settings, items, labels)
    # Cache both directions while each source is open; production baseline stays upright.
    return (items if include_choices else [[choices[0]] for choices in items]), labels
