"""Plan whole-order normal/rotated zones from one shared set of measured items."""
from dataclasses import replace
from math import ceil

from .cutter_planner import plan_cutter_layout, read_cutter_items
from .item_factory import read_items
from .models import mm_to_px
from .order_groups import complete_orders, ordered_paths
from .planner import _place_choice
from .units import UnitChoice, UnitMember
from .zone_optimizer import select_zones
from .batch_analysis import attach_rotation_options
from .size_policy import ordered_single_blocks


def _normal(paths, settings, prepared=None, preserve_sequence=False):
    effective = [settings]
    def report(stage, current, total, filename):
        if stage == '批次刀位已确定':
            effective[0] = replace(settings, cutter_knife_mm=current*25.4/total)
    plan = plan_cutter_layout(paths, settings, report, prepared=prepared, preserve_sequence=preserve_sequence)
    return plan, effective[0]


def rotation_items(paths, settings, progress=None):
    manual = dict(settings.manual_rotations)
    direction = 90 if settings.rotation_direction == 'left' else -90
    rotations = tuple((str(p.resolve()), manual.get(str(p.resolve())) or direction) for p in paths)
    rotated = replace(settings, allow_rotation=False, manual_rotations=rotations,
                      color_block_position='left_top', color_block_offset_y_mm=0)
    options, labels = read_items(paths, rotated, progress)
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    safety = ceil(settings.cutter_safety_mm*settings.dpi/25.4)
    items = {row[0].path: row[0] for row in options if row[0].footprint_width+2*safety < width}
    return items, labels


def _rotated(paths, settings, prepared=None):
    items, labels = prepared if prepared is not None else rotation_items(paths, settings)
    if any(p not in items for p in paths):
        return None
    safety = ceil(settings.cutter_safety_mm*settings.dpi/25.4)
    knife = max(items[p].footprint_width for p in paths)+safety
    spacing = mm_to_px(settings.spacing_mm, settings.dpi)
    margin = mm_to_px(settings.margin_mm, settings.dpi)
    planned, y = [], margin
    for path in paths:
        item = items[path]
        row = UnitChoice(item.footprint_width, item.footprint_height,
                         (UnitMember(item, 0, 0),), 1)
        planned.extend(_place_choice(row, 0, y))
        y += item.footprint_height+spacing
    return planned, labels, y-spacing+margin, knife


def plan_rotation_zones(paths, settings, progress, analysis=None, analysis_ready=None):
    base_settings = replace(settings, cutter_rotation_zone=False,
                           sequence_numbers=settings.sequence_numbers or tuple(
                               (str(p.resolve()), i) for i, p in enumerate(paths, 1)))
    paths = ordered_paths(paths)
    options, labels = read_cutter_items(paths, base_settings, progress)
    normal_items = {row[0].path: row[0] for row in options}
    rotated_items, rotated_labels = rotation_items(paths, base_settings, progress)
    if analysis is not None:
        attach_rotation_options(analysis, rotated_items, settings, analysis_ready)
    baseline, normal_settings = None, base_settings
    try:
        baseline, normal_settings = _normal(paths, base_settings, (options, labels))
    except ValueError:
        # A valid rotated zone can fit orders that have no common normal knife.
        pass
    orders = ordered_single_blocks(complete_orders(paths), coalesce=True)
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
        return _baseline_result(baseline, _normal(paths, base_settings, (options, labels))[1], progress)
    planned = []
    if normal_result:
        planned.extend((path, replace(p, cut_zone='常规区', cut_knife_x_px=knife))
                       for path, p in normal_result[0])
    planned.extend((path, replace(p, y_px=p.y_px+boundary, row_y_px=p.row_y_px+boundary,
                       number_y_px=p.number_y_px+boundary, color_block_y_px=p.color_block_y_px+boundary,
                       cut_zone='旋转区', cut_knife_x_px=rotated[3])) for path, p in rotated[0])
    baseline_height = baseline[3] if baseline else new_height
    if progress:
        progress('批次刀位已确定', knife if normal_result else rotated[3], settings.dpi,
                 '完整订单分区，双面保持相邻；各区刀位固定')
        progress('旋转区节省', baseline_height-new_height, settings.dpi,
                 f'旋转区 {len(rotated_paths)} 张 · 节省 {(baseline_height-new_height)*25.4/settings.dpi/1000:.3f} 米')
    return planned, labels, mm_to_px(settings.media_width_mm, settings.dpi), new_height, baseline_height


def _baseline_result(plan, settings, progress):
    if plan is None:
        raise ValueError('没有可安全使用的整批排版。')
    if progress:
        progress('批次刀位已确定', mm_to_px(settings.cutter_knife_mm, settings.dpi), settings.dpi,
                 '旋转不能减少整批用膜，保持常规排版')
    return plan
