"""Keep only whole orders that meet fixed-knife width and marker rules."""
from automatic_print.layout_engine.cutting.validation.cut_validation import validate_cut_corridor
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.labeling.markers.left_marker import head_margin
from automatic_print.layout_engine.orders.order_groups import order_key
from automatic_print.layout_engine.planning.packing.units import build_units
from ..cutter_planner import cutter_output_width
from ..order_lane_trial import plan_order_sides_rows, trial_order_sides


def plan_order_side_zone(orders, items, lanes, spacing, settings, labels, color_boundary):
    all_paths = [path for order in orders for path in order]
    groups = _groups(all_paths, items, spacing)
    knife = mm_to_px(settings.cutter_knife_mm, settings.dpi)
    trial = trial_order_sides(groups, lanes, spacing, knife)
    if trial['uncertain_order_keys']:
        raise ValueError('订单身份不可靠，不能启用整单归侧：' + '、'.join(
            trial['uncertain_order_keys']))
    blocked = set(trial['unplaceable_orders'])
    good = [order for order in orders if order_key(order[0]) not in blocked]
    bad = [order for order in orders if order_key(order[0]) in blocked]
    while good:
        good, bad = color_boundary(good, bad)
        if not good:
            break
        paths = [path for order in good for path in order]
        planned, height, _trial = plan_order_sides_rows(
            _groups(paths, items, spacing), lanes, spacing, knife,
            head_margin(settings))
        unpaired = _right_only_marker_orders(planned, knife)
        if unpaired:
            bad.extend(order for order in good if order_key(order[0]) in unpaired)
            good = [order for order in good if order_key(order[0]) not in unpaired]
            continue
        width = cutter_output_width(
            planned, settings, mm_to_px(settings.media_width_mm, settings.dpi))
        validate_cut_corridor(planned, settings, width, canvas_height=height)
        return good, bad, (planned, labels, width, height, height)
    return good, bad, None


def _groups(paths, items, spacing):
    return [[member.item for member in choice[0].members]
            for choice in build_units([[items[path]] for path in paths], spacing)]


def _right_only_marker_orders(planned, knife):
    first_rows = {(p.row_y_px, p.y_px) for _path, p in planned if p.x_px < knife}
    return {order_key(path) for path, p in planned
            if p.x_px >= knife and p.color_block_width_px
            and (p.row_y_px, p.y_px) not in first_rows}
