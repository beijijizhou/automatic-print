"""Keep single-sided single orders in size blocks, pairing safe small companions."""
from collections import defaultdict

from .order_groups import order_key
from .source_metadata import size_key, source_size, source_block, block_key
from .size_policy import single_order_size


def prepare_order_sequence(orders, items):
    locked, sizes = [], defaultdict(list)
    order_sizes = {}
    for index, order in enumerate(orders):
        size = single_order_size(order)
        size = source_block(order[0]) if size is not None else None
        order_sizes[index] = size
        if size is not None:
            sizes[size].append(index)
        else:
            locked.append(index)
    pending = [index for size in sorted(sizes, key=block_key)
               for index in sorted(sizes[size], key=lambda i: -items[orders[i][0]].footprint_height)]
    return locked, pending, order_sizes


def lane_fits(item, lane):
    start, end, marker = lane
    if marker is None:
        from .left_marker import external_left_item
        item = external_left_item(item)
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
    from .pairing_index import indexed_sequence
    return indexed_sequence(orders, items, lanes, prepared or prepare_order_sequence(orders, items))


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
