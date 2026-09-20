"""Geometry-only trial: keep every multi-piece order in one cutter lane."""
from collections import OrderedDict

from automatic_print.layout_engine.orders.order_groups import order_key, is_double_pair
from .column_solver import group_rows


def compare_multi_order_lanes(groups, lanes, spacing):
    """Balance measured lane heights, without creating printable placements."""
    if len(lanes) != 2:
        raise ValueError('多件单列试验只比较固定刀位的左右两列。')
    orders = OrderedDict()
    for group in groups:
        if not group:
            raise ValueError('订单中存在空排版单元。')
        key = order_key(group[0].path)
        if any(order_key(item.path) != key for item in group):
            raise ValueError('一个排版单元不能跨订单。')
        if len(group) > 1 and (len(group) != 2 or not is_double_pair(
                group[0].path, group[1].path)):
            raise ValueError('多图单元必须是同件商品的完整双面。')
        orders.setdefault(key, []).append(group)

    candidates, infeasible = [], []
    for key, units in orders.items():
        if len(units) == 1:
            continue  # This first trial deliberately excludes single-piece orders.
        heights = []
        for lane in lanes:
            rows = [group_rows(group, [lane], spacing) for group in units]
            heights.append(None if any(not row for row in rows) else
                           sum(row[0].height for row in rows) + spacing * (len(rows)-1))
        if all(height is None for height in heights):
            infeasible.append(key)
        else:
            candidates.append((key, units, heights))

    # Place lane-constrained orders before flexible ones, then larger orders first.
    candidates.sort(key=lambda entry: (sum(h is not None for h in entry[2]),
                                       -max(h for h in entry[2] if h is not None), entry[0]))
    totals, pieces, assignments = [0, 0], [0, 0], []
    for key, units, heights in candidates:
        feasible = [index for index, height in enumerate(heights) if height is not None]
        lane = min(feasible, key=lambda index: (
            abs(totals[index] + heights[index] + (spacing if totals[index] else 0)
                - totals[1-index]),
            max(totals[index] + heights[index] + (spacing if totals[index] else 0),
                totals[1-index]),
            pieces[index], index,
        ))
        height = heights[lane]
        totals[lane] += height + (spacing if totals[lane] else 0)
        pieces[lane] += len(units)
        assignments.append({'order': key, 'lane': lane, 'pieces': len(units),
                            'images': sum(map(len, units)), 'height_px': height})
    return {'assignments': assignments, 'lane_heights_px': totals,
            'lane_pieces': pieces, 'height_gap_px': abs(totals[0]-totals[1]),
            'unplaceable_orders': infeasible,
            'excluded_single_orders': sum(len(units) == 1 for units in orders.values())}
