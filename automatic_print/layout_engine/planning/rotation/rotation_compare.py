"""Concurrent complete-batch comparisons, without sharing mutable plan state."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import replace
from time import monotonic

from automatic_print.layout_engine.planning.columns.cutter_planner import plan_cutter_layout, read_cutter_items
from automatic_print.layout_engine.planning.rotation.rotation_zones import plan_rotation_zones, rotation_items
from automatic_print.layout_engine.cutting.geometry.transition_marks import marked_height
from automatic_print.layout_engine.cutting.validation.order_validation import validate_order_placements
from automatic_print.layout_engine.cutting.validation.cut_validation import validate_cut_corridor
from automatic_print.layout_engine.labeling.markers.marker_space import validate_embedded_marks


def compare_rotation(paths, settings, progress, analysis, analysis_ready):
    normal_settings = replace(settings, cutter_rotation_zone=False,
                              cutter_tail_rotation=False, allow_rotation=False)
    # Measure each source and both orientations once before plan workers start.
    # Concurrent plans consume immutable geometry and never race to decode a file.
    options, labels = read_cutter_items(
        paths, normal_settings, progress, prepare_rotations=True,
    )
    rotated_items, rotated_labels = rotation_items(
        paths, normal_settings, None,
    )

    def normal_progress(stage, current, total, filename):
        if progress:
            progress('常规方案：'+stage, current, total, filename)

    def checked(fn, config, callback):
        started = monotonic()
        effective = [config]
        def report(stage, current, total, filename):
            if stage == '批次刀位已确定':
                effective[0] = replace(config, cutter_knife_mm=current*25.4/total)
            if callback:
                callback(stage, current, total, filename)
        try:
            result = fn(paths, config, report)
            if config.cutter_knife_change_gap_mm > 0:
                from automatic_print.layout_engine.cutting.geometry.knife_change_gap import apply_knife_change_gap
                result, _changes = apply_knife_change_gap(result, config)
            planned, _, width, height = result[:4]
            validate_order_placements(paths, planned)
            validate_cut_corridor(planned, effective[0], width)
            validate_embedded_marks(planned, config)
            return result, marked_height(planned, config, width, height), monotonic()-started, ''
        except ValueError as exc:
            return None, None, monotonic()-started, str(exc)

    workers = min(2, max(1, settings.film_geometry_workers))
    if progress:
        progress('比较旋转区域', 0, 2, f'最多{workers}路计算常规方案与完整订单旋转方案')
    def normal_plan(paths, config, report):
        return plan_cutter_layout(
            paths, config, report, prepared=(options, labels),
        )

    def rotation_plan(paths, config, report):
        return plan_rotation_zones(
            paths, config, report, analysis, analysis_ready,
            prepared=(options, labels, rotated_items, rotated_labels),
        )
    if workers == 1:
        normal = checked(normal_plan, normal_settings, normal_progress)
        rotated = checked(rotation_plan, settings, progress)
    else:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='layout-compare') as pool:
            normal = pool.submit(copy_context().run, checked, normal_plan, normal_settings, normal_progress)
            rotated = pool.submit(copy_context().run, checked, rotation_plan, settings, progress)
            normal, rotated = normal.result(), rotated.result()
    if settings.cutter_majority_two_zone:
        from automatic_print.layout_engine.planning.columns.adaptive_knife import plan_adaptive_knife_zones
        def adaptive_plan(paths, config, report):
            return plan_adaptive_knife_zones(
                paths, config, report,
                prepared=(options, labels, rotated_items, rotated_labels),
            )
        adaptive = checked(adaptive_plan, settings, progress)
    else:
        adaptive = (None, None, 0, '“多数并排集中在一起”未启用')
    if adaptive[0] is not None:
        strategy, selected = '多数并排区 + 剩余旋转区', adaptive
    elif rotated[0] is not None:
        strategy, selected = '旋转区域', rotated
    elif normal[0] is not None:
        strategy, selected = '常规方案（旋转候选不可用）', normal
    else:
        raise ValueError(
            '常规、旋转及连续刀位分区均无法安全生成：'
            + normal[3] + '；' + rotated[3] + '；' + adaptive[3]
        )
    result, height, seconds, _ = selected
    normal_height = normal[1]
    scale = 25.4/settings.dpi/1000
    analysis['rotation_comparison'] = {
        'normal_m': normal_height*scale if normal_height is not None else None,
        'rotation_m': height*scale,
        'saved_m': (normal_height-height)*scale if normal_height is not None else None,
        'normal_seconds': normal[2], 'rotation_seconds': seconds,
        'normal_error': normal[3], 'parallelism': workers,
        'rotated_images': sum(bool(p.rotation_degrees) for _, p in result[0]),
        'selected_strategy': strategy,
        'selected_zones': len({p.cut_zone for _, p in result[0]}),
    }
    if progress:
        progress('比较旋转区域', 2, 2, '两套整批方案已完成订单、双面、刀位与透明标记检查')
    # The caller adds selected-plan decorations to both length fields.
    extra = height-result[3]
    baseline = (normal_height if normal_height is not None else height)-extra
    return result[0], result[1], result[2], result[3], baseline


def update_selected_comparison(comparison, result, settings, whole_rotation=False):
    if not comparison:
        return
    if whole_rotation:
        comparison['selected_strategy'] = '整批旋转'
    height = marked_height(result[0], settings, result[2], result[3])
    comparison['rotation_m'] = height*25.4/settings.dpi/1000
    normal = comparison['normal_m']
    comparison['saved_m'] = normal-comparison['rotation_m'] if normal is not None else None
    comparison['rotated_images'] = sum(bool(p.rotation_degrees) for _, p in result[0])
    comparison['selected_zones'] = len({p.cut_zone for _, p in result[0]})
