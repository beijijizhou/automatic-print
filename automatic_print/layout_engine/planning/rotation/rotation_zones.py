"""Plan whole-order normal/rotated zones from one shared set of measured items."""
from dataclasses import replace
from math import ceil

from automatic_print.layout_engine.planning.columns.cutter_planner import plan_cutter_layout, read_cutter_items
from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.orders.order_groups import complete_orders, ordered_paths
from automatic_print.layout_engine.planning.zones.zone_optimizer import select_zones
from automatic_print.layout_engine.orders.batch_analysis import attach_rotation_options
from automatic_print.layout_engine.orders.size_policy import ordered_single_blocks
from automatic_print.layout_engine.cutting.geometry.transition_marks import rotation_marker_item, marked_height
from automatic_print.layout_engine.measurement.measurement_session import resolved_name


def _normal(paths, settings, prepared=None, preserve_sequence=False):
    effective = [settings]
    def report(stage, current, total, filename):
        if stage == '批次刀位已确定':
            effective[0] = replace(settings, cutter_knife_mm=current*25.4/total)
    plan = plan_cutter_layout(paths, settings, report, prepared=prepared, preserve_sequence=preserve_sequence)
    return plan, effective[0]


def rotation_items(paths, settings, progress=None, prepared=None):
    from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
    original_paths = paths
    sequence = settings.sequence_numbers or tuple((resolved_name(p), i)
                                                for i, p in enumerate(paths, 1))
    if prepared is None:
        from automatic_print.layout_engine.measurement.cutter_measurements import load_cutter_measurements
        prepared = load_cutter_measurements(original_paths, replace(
            settings, allow_rotation=True, manual_rotations=(),
            color_block_position='left_top', color_block_offset_y_mm=0,
        ))
    if settings.platform_name:
        paths = [p for p in paths if detect_guide_band(p) is not None]
    if not paths:
        return {}, {}
    manual = dict(settings.manual_rotations)
    direction = 90 if settings.rotation_direction == 'left' else -90
    rotations = tuple((resolved_name(p), manual.get(resolved_name(p)) or direction) for p in paths)
    rotated = replace(settings, allow_rotation=False, manual_rotations=rotations,
                      cutter_mode='single' if settings.cutter_mode=='free' and settings.color_block_enabled else settings.cutter_mode,
                      color_block_position='left_top', color_block_offset_y_mm=0,
                      sequence_numbers=sequence)
    if prepared is not None:
        measured, labels = prepared
        by_path = {row[0].path: row for row in measured}
        options = [by_path[path] for path in paths if path in by_path]
    else:
        options, labels = read_items(paths, rotated, progress)
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    safety = ceil(settings.cutter_safety_mm*settings.dpi/25.4)
    items = {}
    for row in options:
        candidate = next((item for item in row if item.rotation_degrees), None)
        if candidate is None:
            continue
        item = rotation_marker_item(candidate, settings)
        if (item.footprint_width+2*safety >= width if settings.cutter_mode == 'dual' else item.footprint_width > width):
            continue
        try:
            items[row[0].path] = item
        except ValueError:
            # Unsafe automatic candidates stay in the normal zone, never disappear.
            continue
    return items, labels


def _rotated(paths, settings, prepared=None):
    items, labels = prepared if prepared is not None else rotation_items(paths, settings)
    if any(p not in items for p in paths):
        return None
    # Rotation changes the real footprint. Feed those measured footprints back
    # through the one shared automatic-column planner so film width decides
    # whether the result is one, two or more columns. Production order remains
    # fixed and complete orders are still indivisible.
    rotated_settings = replace(
        settings, cutter_auto_knife=settings.cutter_mode == 'dual',
        allow_rotation=False, manual_rotations=(),
        # This flag partitions the outer normal/rotation zones. Once inside
        # the rotation zone, same-colour/same-size singles must be free to find
        # the best fixed-lane companions.
        cutter_majority_two_zone=False,
    )
    plan = plan_cutter_layout(
        paths, rotated_settings, None,
        prepared=([[items[path]] for path in paths], labels),
        preserve_sequence=False,
    )
    planned = [(path, replace(placement, cut_zone='旋转区'))
               for path, placement in plan[0]]
    knives = next((p.cut_knife_xs_px for _path, p in planned
                   if p.cut_knife_xs_px), ())
    primary = knives[0] if knives else 0
    return planned, labels, plan[3], primary


def plan_rotation_zones(paths, settings, progress, analysis=None, analysis_ready=None, prepared=None,
                        normal_baseline=None):
    base_settings = replace(settings, cutter_rotation_zone=False,
                           sequence_numbers=settings.sequence_numbers or tuple(
                               (resolved_name(p), i) for i, p in enumerate(paths, 1)))
    paths = ordered_paths(paths)
    options, labels = prepared[:2] if prepared else read_cutter_items(paths, base_settings, progress)
    normal_items = {row[0].path: row[0] for row in options}
    baseline, normal_settings = None, base_settings
    if normal_baseline is not None:
        baseline, normal_settings = normal_baseline
    else:
        try:
            baseline, normal_settings = _normal(paths, base_settings, (options, labels))
        except ValueError:
            # A valid rotated zone can fit orders that have no common normal knife.
            pass
    from .single_rotation import eligible_tail, plan_single_rotation
    tail = eligible_tail(paths, baseline)
    rotated_items, rotated_labels = (prepared[2:] if prepared else rotation_items(
        tail if tail is not None else paths, base_settings, progress))
    if analysis is not None:
        attach_rotation_options(analysis, rotated_items, settings, analysis_ready)
        if tail is not None:
            allowed = {str(p) for p in tail}
            for order in analysis['orders']:
                if any(im['path'] not in allowed for it in order['items'] for im in it['images']):
                    order['rotation_policy_skip'] = True
    if tail is not None:
        return plan_single_rotation(baseline, tail, rotated_items, rotated_labels, normal_settings, progress)
    orders = ordered_single_blocks(complete_orders(paths), coalesce=True)
    baseline_settings = normal_settings
    mask, knife, _, sequence = select_zones(orders, normal_items, rotated_items, base_settings, progress)
    orders = [orders[i] for i in sequence]
    if not mask:
        return _baseline_result(baseline, normal_settings, progress)
    rotated_paths = [p for i, order in enumerate(orders) if mask & (1 << i) for p in order]
    normal_paths = [p for i, order in enumerate(orders) if not mask & (1 << i) for p in order]
    normal_settings = replace(base_settings, cutter_auto_knife=False,
                              cutter_knife_mm=knife*25.4/settings.dpi)
    normal_result = None
    if normal_paths:
        normal_result, _ = _normal(normal_paths, normal_settings,
                                  ([[normal_items[p]] for p in normal_paths], labels), preserve_sequence=True)
    rotated = _rotated(rotated_paths, base_settings, (rotated_items, rotated_labels))
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    boundary = normal_result[3]+spacing if normal_result else 0
    new_height = boundary+rotated[2]
    if baseline and new_height >= baseline[3]:
        return _baseline_result(baseline, baseline_settings, progress)
    planned = []
    if normal_result:
        planned.extend((path, replace(p, cut_zone='常规区', cut_knife_x_px=knife))
                       for path, p in normal_result[0])
    planned.extend((path, replace(p, y_px=p.y_px+boundary, row_y_px=p.row_y_px+boundary,
                       number_y_px=p.number_y_px+boundary, color_block_y_px=p.color_block_y_px+boundary,
                       platform_y_px=p.platform_y_px+boundary,
                       cut_zone='旋转区')) for path, p in rotated[0])
    # The old zone optimizer estimates rotated work as one image per row. Its
    # mixed candidate remains useful, but a whole rotated batch may become
    # shorter only after the shared multi-column solver sees all neighbours.
    # Always compare that exact candidate before selecting the production plan.
    whole = _rotated(paths, base_settings, (rotated_items, rotated_labels))
    if whole is not None and whole[2] < new_height:
        planned, labels, new_height = whole[0], whole[1], whole[2]
        normal_result, normal_paths, rotated_paths = None, [], list(paths)
        knife = whole[3]
    baseline_height = baseline[3] if baseline else new_height
    from automatic_print.layout_engine.orders.color_policy import validate_color_order
    try:
        validate_color_order(planned)
    except ValueError:
        if baseline is not None:
            return _baseline_result(baseline,baseline_settings,progress)
        raise
    if settings.transition_lines or settings.batch_footer_enabled or settings.batch_end_block:
        width = mm_to_px(settings.media_width_mm, settings.dpi)
        new_height = marked_height(planned, settings, width, new_height)
        baseline_height = marked_height(baseline[0], settings, width, baseline[3]) if baseline else new_height
        if baseline and new_height >= baseline_height:
            return _baseline_result(baseline, baseline_settings, progress)
    if progress:
        progress('批次刀位已确定', knife if normal_result else rotated[3], settings.dpi,
                 '完整订单分区，双面保持相邻；各区刀位固定')
        progress('旋转区节省', baseline_height-new_height, settings.dpi,
                 f'旋转区 {len(rotated_paths)} 张 · 节省 {(baseline_height-new_height)*25.4/settings.dpi/1000:.3f} 米')
    from automatic_print.layout_engine.planning.columns.cutter_planner import cutter_output_width
    width = cutter_output_width(planned, settings,
                                mm_to_px(settings.media_width_mm, settings.dpi))
    return planned, labels, width, new_height, baseline_height


def _baseline_result(plan, settings, progress):
    if plan is None:
        raise ValueError('没有可安全使用的整批排版。')
    if progress:
        progress('批次刀位已确定', mm_to_px(settings.cutter_knife_mm, settings.dpi), settings.dpi,
                 '旋转不能减少整批用膜，保持常规排版')
    return plan
