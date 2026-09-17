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
    from automatic_print.layout_engine.domain.models import mm_to_px
    from automatic_print.layout_engine.labeling.markers.left_marker import head_margin
    from automatic_print.layout_engine.planning.columns.choice_cutter import riin_sequence_height
    riin_height = riin_sequence_height(
        [row[0] for row in options],
        mm_to_px(settings.media_width_mm, settings.dpi),
        mm_to_px(settings.spacing_mm, settings.dpi),
        head_margin(settings),
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
            validate_cut_corridor(planned, effective[0], width, 0, result[3])
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
    if settings.developer_compact_cutter_layout:
        from automatic_print.layout_engine.planning.columns.choice_cutter import plan_choice_cutter_layout

        normal_by_path = {row[0].path: row[0] for row in options}
        choice_items = [[normal_by_path[path], *(
            [rotated_items[path]] if path in rotated_items else [])]
            for path in paths]

        def sequence_choice_plan(_paths, config, _report):
            return plan_choice_cutter_layout(
                paths, config, choice_items, labels | rotated_labels,
                mm_to_px(config.spacing_mm, config.dpi),
                preserve_sequence=True,
            )

        sequence_choice = checked(sequence_choice_plan, settings, progress)
    else:
        sequence_choice = (None, None, 0, '开发者顺序旋转优化未启用')
    candidates = []
    if normal[0] is not None:
        candidates.append((normal[1], 0, '常规固定刀位方案', normal))
    if rotated[0] is not None:
        candidates.append((rotated[1], 1, '旋转区域', rotated))
    if adaptive[0] is not None:
        candidates.append((adaptive[1], 2, '多数并排区 + 剩余旋转区', adaptive))
    if sequence_choice[0] is not None:
        candidates.append((sequence_choice[1], 1, '顺序旋转候选', sequence_choice))
    if not candidates:
        raise ValueError(
            '常规、旋转及连续刀位分区均无法安全生成：'
            + normal[3] + '；' + rotated[3] + '；' + adaptive[3]
        )
    if settings.developer_compact_cutter_layout:
        _height, _complexity, strategy, selected = min(candidates)
    elif adaptive[0] is not None:
        strategy, selected = '多数并排区 + 剩余旋转区', adaptive
    elif rotated[0] is not None:
        strategy, selected = '旋转区域', rotated
    else:
        strategy, selected = '常规方案（旋转候选不可用）', normal
    result, height, seconds, _ = selected
    normal_height = normal[1]
    scale = 25.4/settings.dpi/1000
    candidate_lengths = {
        name: candidate[1]*scale
        for _candidate_height, _complexity, name, candidate in candidates
    }
    candidate_errors = {
        name: candidate[3]
        for name, candidate in (
            ('常规固定刀位方案', normal),
            ('旋转区域', rotated),
            ('多数并排区 + 剩余旋转区', adaptive),
            ('顺序旋转候选', sequence_choice),
        ) if candidate[0] is None and candidate[3]
    }
    analysis['rotation_comparison'] = {
        'normal_m': normal_height*scale if normal_height is not None else None,
        'rotation_m': height*scale,
        'saved_m': (normal_height-height)*scale if normal_height is not None else None,
        'normal_seconds': normal[2], 'rotation_seconds': seconds,
        'normal_error': normal[3], 'parallelism': workers,
        'rotated_images': sum(bool(p.rotation_degrees) for _, p in result[0]),
        'selected_strategy': strategy,
        'selected_zones': len({p.cut_zone for _, p in result[0]}),
        'riin_sequence_m': riin_height*scale,
        'riin_improvement_m': (riin_height-height)*scale,
        'riin_goal_met': height <= riin_height,
        'candidate_lengths_m': candidate_lengths,
        'candidate_errors': candidate_errors,
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
    riin = comparison.get('riin_sequence_m')
    if riin is not None:
        comparison['riin_improvement_m'] = riin-comparison['rotation_m']
        comparison['riin_goal_met'] = comparison['rotation_m'] <= riin
