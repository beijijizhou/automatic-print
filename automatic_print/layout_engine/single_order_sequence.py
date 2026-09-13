"""Keep single-sided single orders in size blocks, pairing safe small companions."""
from collections import defaultdict

from .order_groups import order_key, pair_identity
from .source_metadata import is_small_item, size_key, source_size


def arrange_orders(orders, items, lanes, settings):
    from .cutter_planner import _horizontal

    locked, sizes = [], defaultdict(list)
    for index, order in enumerate(orders):
        eligible = (len(order) == 1 and pair_identity(order[0]) is not None
                    and pair_identity(order[0])[1] == '1'
                    and order_key(order[0]) != '未识别订单组'
                    and source_size(order[0]) != '未识别尺码')
        if eligible:
            sizes[source_size(order[0])].append(index)
        else:
            locked.append(index)
    pending = [index for size in sorted(sizes, key=size_key)
               for index in sorted(sizes[size], key=lambda i: -items[orders[i][0]].footprint_height)]
    ordered = list(locked)
    while pending:
        first = pending.pop(0)
        ordered.append(first)
        a = items[orders[first][0]]
        candidates = []
        for position, index in enumerate(pending):
            b = items[orders[index][0]]
            same = source_size(a.path) == source_size(b.path)
            small = is_small_item(a, settings.dpi) or is_small_item(b, settings.dpi)
            if not same and not small:
                continue
            row = _horizontal([a, b], lanes)
            if row is None:
                continue
            saved = a.footprint_height+b.footprint_height-row.height
            if saved > 0:
                candidates.append((not same, -saved, position, index))
        if candidates:
            partner = min(candidates)[-1]
            ordered.append(partner)
            pending.remove(partner)
    return ordered


def arrange_groups(groups, lanes, settings):
    from .order_groups import complete_orders

    items = {item.path: item for group in groups for item in group}
    orders = complete_orders(list(items))
    by_order = defaultdict(list)
    for group in groups:
        by_order[order_key(group[0].path)].append(group)
    sequence = arrange_orders(orders, items, lanes, settings)
    return [group for index in sequence for group in by_order[order_key(orders[index][0])]]
