from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from automatic_print.layout_engine.orders.order_groups import ordered_paths
from automatic_print.layout_engine.orders.batch_analysis import analyze_batch, finish_analysis
from automatic_print.layout_engine.cutting.geometry.transition_marks import marked_height
from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.layout_engine.reporting.metrics import basic_ordered_height
from automatic_print.layout_engine.domain.models import LayoutSettings, ProgressCallback, mm_to_px
from automatic_print.layout_engine.planning.base.row_optimizer import (
    optimal_ordered_layout, place_rows, used_canvas_width,
)
from automatic_print.layout_engine.planning.packing.units import build_units, optimizer_options
from automatic_print.layout_engine.measurement.measurement_session import resolved_name
def plan_layout(
    paths: list[Path],
    settings: LayoutSettings,
    progress: ProgressCallback | None,
    analysis_ready=None,
    ) -> tuple[list[tuple[Path, Placement]], dict[int, str], int, int, int]:
    from automatic_print.layout_engine.measurement.measurement_session import measurement_session
    from automatic_print.layout_engine.planning.cache.cached_planner import plan_with_cache
    with measurement_session() as session:
        return plan_with_cache(_measured_plan, paths, settings, progress, analysis_ready, session)
def _measured_plan(paths, settings, progress, analysis_ready):
    settings = replace(settings, sequence_numbers=settings.sequence_numbers or
                       tuple((resolved_name(path), i) for i, path in enumerate(paths, 1)),
                       label_sequence_total=settings.label_sequence_total or len(paths))
    paths = ordered_paths(paths)
    from automatic_print.layout_engine.planning.zones.pair_width import apply_pair_width_cap
    settings = apply_pair_width_cap(paths, settings, progress)
    analysis = analyze_batch(paths, settings, progress, analysis_ready)
    analysis['width_adjustments'] = settings.width_adjustments
    try:
        result = _plan_layout(paths, settings, progress, analysis, analysis_ready)
    except ValueError as error:
        from automatic_print.layout_engine.planning.rotation.whole_rotation import recover_normal_width
        result = recover_normal_width(paths,settings,progress,error)
        analysis['rotation_recovery']={'reason':str(error),'action':'常规方案无解，采用原尺寸整批旋转单排；未缩小图片'}
    if settings.cutter_mode in {'single', 'dual'}:
        developer_knife_gap = settings.cutter_knife_change_gap_mm > 0
        if developer_knife_gap:
            from automatic_print.layout_engine.cutting.geometry.knife_change_gap import apply_knife_change_gap
            result, _changes = apply_knife_change_gap(result, settings)
        from automatic_print.layout_engine.planning.rotation.whole_rotation import compare_whole
        previously_selected = result
        comparison = analysis.get('rotation_comparison')
        if not settings.strict_fixed_knife and not (comparison and comparison.get('selected_strategy') == '多数并排区 + 剩余旋转区'):
            result = compare_whole(paths, settings, progress, result)
        from automatic_print.layout_engine.planning.rotation.rotation_compare import update_selected_comparison
        update_selected_comparison(comparison, result, settings,
                                   result is not previously_selected)
        if developer_knife_gap:
            result, knife_changes = apply_knife_change_gap(result, settings)
            if knife_changes:
                analysis['knife_change_gap'] = knife_changes
    planned, labels, width, height, baseline = result
    from automatic_print.layout_engine.planning.zones.pair_width import remove_rotated_pair_width_adjustments
    settings = remove_rotated_pair_width_adjustments(settings, planned)
    analysis['width_adjustments'] = settings.width_adjustments
    if settings.batch_end_block:
        width = mm_to_px(settings.media_width_mm,settings.dpi)
    extra = marked_height(planned, settings, width, height)-height
    result = planned, labels, width, height+extra, baseline+extra
    if settings.compare_film_sizes and settings.cutter_mode != 'free':
        from automatic_print.layout_engine.planning.film.film_comparison import compare_films
        analysis['film_comparison'] = compare_films(paths, settings, progress, result)
    from automatic_print.layout_engine.intake.metadata.image_anomalies import collect_image_anomalies
    analysis['image_anomalies'] = collect_image_anomalies(paths, settings, result[0])
    analysis['image_anomalies'].extend(
        {'source': name, 'path': path, 'kind': text,
         'action': '已按开发者设置等比缩小；请核对预览和实际烫印尺寸'}
        for name, text, path in settings.width_adjustments
        if text.startswith(('所选尺码并排宽度上限：', '共刀并排等比缩小：'))
    )
    if analysis.get('rotation_recovery'):
        analysis['image_anomalies'].append({'source':'整批旋转恢复','kind':analysis['rotation_recovery']['action'],
                                          'action':'请核查旋转区预览与统一刀位；常规基准无解，不显示虚假省膜量'})
    if analysis_ready:
        analysis_ready(finish_analysis(analysis, result[0], settings, result[3], result[4]))
    return result
def _plan_layout(paths, settings, progress, analysis, analysis_ready):
    if settings.cutter_mode != "free":
        if settings.strict_fixed_knife:
            from automatic_print.layout_engine.planning.columns.adaptive_knife import plan_adaptive_knife_zones
            return plan_adaptive_knife_zones(paths, settings, progress)
        if settings.cutter_mode == 'single' and settings.cutter_single_row_rotation:
            from .single_rows import plan_single_rows
            return plan_single_rows(paths,settings,progress)
        if (settings.cutter_rotation_zone or settings.cutter_majority_two_zone) and settings.cutter_mode == "dual":
            from automatic_print.layout_engine.planning.rotation.rotation_compare import compare_rotation
            return compare_rotation(paths, settings, progress, analysis, analysis_ready)
        if settings.cutter_tail_rotation and settings.cutter_mode == 'dual':
            from automatic_print.layout_engine.planning.rotation.tail_rotation import plan_tail_rotation
            return plan_tail_rotation(paths, settings, progress)
        from automatic_print.layout_engine.planning.columns.cutter_planner import plan_cutter_layout
        return plan_cutter_layout(paths, settings, progress)
    canvas_width = mm_to_px(settings.media_width_mm, settings.dpi)
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    usable_width = canvas_width
    if usable_width <= 0:
        raise ValueError("外边距过大，画布没有可打印区域。")
    items, labels = read_items(paths, settings, progress)
    if progress:
        progress('计算排版', 0, len(paths), '开始整批顺序排版计算')
    units = build_units(items, spacing)
    double_count = sum(
        len(choices[0].members) == 2 for choices in units
    )
    if progress and double_count:
        progress(
            "整理双面图片",
            double_count,
            double_count,
            f"已识别 {double_count} 组双面图片",
        )
    for choices in units:
        if all(choice.width > usable_width for choice in choices):
            name = choices[0].members[0].item.path.name
            from automatic_print.layout_engine.diagnostics.error_parameters import choices_failure
            raise ValueError(f"图片组 {name} 超过了材料可打印宽度。\n"+choices_failure(choices,settings,usable_width))
    rows = optimal_ordered_layout(
        optimizer_options(units), usable_width, spacing
    )
    planned = place_rows(units, rows, margin, spacing)
    canvas_height = (
        max(
            placement.row_y_px + placement.footprint_height_px
            for _path, placement in planned
        )
        + margin
    )
    baseline = [_baseline_choice(choices, usable_width) for choices in units]
    baseline_height = (
        basic_ordered_height(baseline, usable_width, spacing) + 2 * margin
    )
    used_width = min(canvas_width, used_canvas_width(planned))
    return planned, labels, used_width, canvas_height, baseline_height


def _baseline_choice(choices, usable_width):
    fitting = next(
        (choice for choice in choices if choice.width <= usable_width),
        None,
    )
    if fitting is None:
        raise ValueError("至少一个图片组超过了材料可打印宽度。")
    return fitting.width, fitting.height
