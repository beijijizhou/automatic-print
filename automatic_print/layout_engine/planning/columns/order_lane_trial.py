"""Isolated two-lane trial: a complete order never crosses the middle knife."""
from collections import Counter, OrderedDict
from dataclasses import replace

from automatic_print.layout_engine.orders.order_groups import order_key, is_double_pair
from automatic_print.layout_engine.planning.base.row_optimizer import _place_choice
from .column_solver import group_rows


def trial_order_sides(groups, lanes, spacing, knife_x):
    """Return diagnostic coordinates, never a production-approved layout."""
    if (len(lanes) != 2 or lanes[0][0] != 0 or lanes[0][2] is not None
            or lanes[0][1] > knife_x or lanes[1][0] < knife_x
            or lanes[1][2] is None):
        raise ValueError('整单归侧试验需要两列和一条固定中间刀位。')
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
    if not orders:
        raise ValueError('没有可测试的订单。')

    candidates, blocked = [], []
    for key, units in orders.items():
        lane_rows = [[group_rows(group, [lane], spacing) for group in units]
                     for lane in lanes]
        heights = [None if any(not options for options in rows) else
                   sum(options[0].height for options in rows) + spacing * (len(rows)-1)
                   for rows in lane_rows]
        if all(height is None for height in heights):
            blocked.append(key)
        else:
            candidates.append((key, units, heights, lane_rows))

    # Forced-side orders first, then longest orders. Placement within each lane
    # is reconstructed in original batch order, so each strip has intact orders.
    candidates.sort(key=lambda entry: (sum(h is not None for h in entry[2]),
                                       -max(h for h in entry[2] if h is not None), entry[0]))
    assigned, totals, pieces = {}, [0, 0], [0, 0]
    for key, units, heights, _rows in candidates:
        feasible = [index for index, height in enumerate(heights) if height is not None]
        lane = min(feasible, key=lambda index: (
            abs(totals[index] + heights[index] + (spacing if totals[index] else 0)
                - totals[1-index]),
            max(totals[index] + heights[index] + (spacing if totals[index] else 0),
                totals[1-index]), pieces[index], index))
        assigned[key] = lane
        totals[lane] += heights[lane] + (spacing if totals[lane] else 0)
        pieces[lane] += len(units)

    if blocked:
        return _report(orders, assigned, totals, pieces, blocked, [])
    plans = {key: (units, lane_rows[assigned[key]])
             for key, units, _heights, lane_rows in candidates}
    planned, lane_heights = [], [0, 0]
    for lane_index in (0, 1):
        y = 0
        for key in orders:
            if assigned[key] != lane_index:
                continue
            units, rows = plans[key]
            for _group, options in zip(units, rows, strict=True):
                row = options[0]
                planned.extend((path, replace(placement, cut_zone='并排区',
                    cut_knife_x_px=knife_x, cut_knife_xs_px=(knife_x,),
                    cut_column_count=2)) for path, placement in _place_choice(row, 0, y))
                y += row.height + spacing
        lane_heights[lane_index] = max(0, y-spacing)
    expected = Counter(item.path for group in groups for item in group)
    if Counter(path for path, _placement in planned) != expected:
        raise ValueError('试验坐标丢失或重复源图片。')
    return _report(orders, assigned, lane_heights, pieces, blocked, planned)


def _report(orders, assigned, heights, pieces, blocked, planned):
    return {'assignments': [{'order': key, 'lane': assigned.get(key),
                             'pieces': len(units), 'images': sum(map(len, units))}
                            for key, units in orders.items()],
            'lane_heights_px': heights, 'lane_pieces': pieces,
            'height_px': max(heights) if not blocked else None,
            'height_gap_px': abs(heights[0]-heights[1]) if not blocked else None,
            'unplaceable_orders': blocked, 'planned': planned,
            'uncertain_order_keys': [key for key in orders if key.startswith('无图印花cvc')]}
