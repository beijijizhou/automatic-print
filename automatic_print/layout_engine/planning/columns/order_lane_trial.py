"""Geometry-only trial for an entire multi-piece batch in one uncut column."""
from collections import OrderedDict

from automatic_print.layout_engine.orders.order_groups import order_key, is_double_pair
from .column_solver import group_rows


def trial_single_column_multi_batch(groups, lane, spacing):
    """Keep every order in one full-width lane; never create printable placements."""
    if lane[0] != 0 or lane[2] is not None:
        raise ValueError('整批单列试验只能使用没有中间纵刀的完整可打印宽度。')
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

    rows, blocked = [], []
    for key, units in orders.items():
        options = [group_rows(group, [lane], spacing) for group in units]
        if any(not choice for choice in options):
            blocked.append(key)
            continue
        height = sum(choice[0].height for choice in options) + spacing * (len(units)-1)
        rows.append({'order': key, 'pieces': len(units),
                     'images': sum(map(len, units)), 'height_px': height})
    # An incomplete batch is only a diagnostic, never an accepted layout.
    height = (sum(row['height_px'] for row in rows) + spacing * (len(rows)-1)
              if not blocked and rows else 0 if not blocked else None)
    return {'orders': rows, 'order_count': len(orders),
            'piece_count': sum(len(units) for units in orders.values()),
            'image_count': sum(len(group) for units in orders.values() for group in units),
            'height_px': height, 'unplaceable_orders': blocked,
            'uncertain_order_keys': [key for key in orders if key.startswith('无图印花cvc')]}
