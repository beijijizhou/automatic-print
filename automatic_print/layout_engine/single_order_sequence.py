"""Keep single-sided single orders in size blocks, pairing safe small companions."""
from collections import defaultdict

from .order_groups import order_key
from .source_metadata import size_key, source_size
from .size_policy import single_order_size


def prepare_order_sequence(orders, items):
    locked, sizes = [], defaultdict(list)
    order_sizes = {}
    for index, order in enumerate(orders):
        size = single_order_size(order)
        order_sizes[index] = size
        if size is not None:
            sizes[size].append(index)
        else:
            locked.append(index)
    pending = [index for size in sorted(sizes, key=size_key)
               for index in sorted(sizes[size], key=lambda i: -items[orders[i][0]].footprint_height)]
    return locked, pending, order_sizes


def lane_fits(item, lane):
    start, end, marker = lane
    x = start if marker is None else marker-item.block_rx
    return x >= start and x+item.footprint_width <= end


def horizontal_savings(a, b, lanes, fits=None):
    """Numeric feasibility equivalent to _horizontal, without placement objects."""
    if len(lanes) != 2 or a.rotation_degrees or b.rotation_degrees:
        return None
    af = fits[a.path] if fits is not None else tuple(lane_fits(a, lane) for lane in lanes)
    bf = fits[b.path] if fits is not None else tuple(lane_fits(b, lane) for lane in lanes)
    if not ((af[0] and bf[1]) or (af[1] and bf[0])):
        return None
    anchor = max(a.image_ry, b.image_ry)
    height = max(a.footprint_height+anchor-a.image_ry,
                 b.footprint_height+anchor-b.image_ry)
    return a.footprint_height+b.footprint_height-height


def arrange_orders(orders, items, lanes, settings, prepared=None):
    locked, pending, order_sizes = prepared or prepare_order_sequence(orders, items)
    pending = list(pending)
    fits = {path: tuple(lane_fits(item, lane) for lane in lanes) for path, item in items.items()}
    ordered = list(locked)
    while pending:
        first = pending.pop(0)
        ordered.append(first)
        a = items[orders[first][0]]
        if len(orders[first]) != 1:
            continue
        candidates = []
        for position, index in enumerate(pending):
            b = items[orders[index][0]]
            if len(orders[index]) != 1:
                continue
            if order_sizes[first] != order_sizes[index]:
                continue
            saved = horizontal_savings(a, b, lanes, fits)
            if saved is None:
                continue
            if saved > 0:
                candidates.append((-saved, position, index))
        if candidates:
            partner = min(candidates)[-1]
            ordered.append(partner)
            pending.remove(partner)
    return ordered


def prepare_groups(groups):
    from .order_groups import complete_orders

    items = {item.path: item for group in groups for item in group}
    orders = complete_orders(list(items))
    by_order = defaultdict(list)
    for group in groups:
        by_order[order_key(group[0].path)].append(group)
    return orders, items, by_order, prepare_order_sequence(orders, items)


def arrange_groups(groups, lanes, settings, prepared=None):
    orders, items, by_order, order_sequence = prepared or prepare_groups(groups)
    sequence = arrange_orders(orders, items, lanes, settings, order_sequence)
    return [group for index in sequence for group in by_order[order_key(orders[index][0])]]
