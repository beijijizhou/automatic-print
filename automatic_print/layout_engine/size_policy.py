"""Single-piece size blocks are production constraints, not packing hints."""
from collections import defaultdict
from .order_groups import order_key, pair_identity
from .source_metadata import source_size, size_key


def single_order_size(order):
    identities = [pair_identity(path) for path in order]
    if (order_key(order[0]) == '未识别订单组' or not all(identities)
            or len({identity[0] for identity in identities}) != 1
            or sorted(identity[1] for identity in identities) not in [['1'], ['1', '2']]):
        return None
    sizes = {source_size(path) for path in order}
    return sizes.pop() if len(sizes) == 1 and '未识别尺码' not in sizes else None


def ordered_single_blocks(orders, coalesce=False):
    locked, sizes = [], defaultdict(list)
    for order in orders:
        size = single_order_size(order)
        if size is None:
            locked.append(order)
        else:
            sizes[size].append(order)
    result = list(locked)
    for size in sorted(sizes, key=size_key):
        members = sizes[size]
        result.extend([[path for order in members for path in order]] if coalesce else members)
    return result


def same_single_size(first, second):
    one, two = single_order_size([first]), single_order_size([second])
    if one is not None:
        return one == two
    return (source_size(first) == source_size(second) == '未识别尺码'
            and all(pair_identity(path) and pair_identity(path)[1] == '1' for path in (first, second)))


def coalesced_size(order):
    from .order_groups import complete_orders
    sizes = {single_order_size(group) for group in complete_orders(order)}
    return sizes.pop() if len(sizes) == 1 and None not in sizes else None


def validate_single_size_blocks(paths, planned):
    from .order_groups import complete_orders
    eligible = {path: size for order in complete_orders(paths)
                if (size := single_order_size(order)) is not None for path in order}
    closed, previous, zones = set(), None, defaultdict(set)
    for path, placement in sorted(planned, key=lambda entry: (entry[1].row_y_px, entry[1].x_px)):
        size = eligible.get(path)
        if size != previous:
            if previous is not None:
                closed.add(previous)
            if size in closed:
                raise ValueError(f'单件尺码 {size} 被其他尺码或订单打散，禁止输出。')
            previous = size
        if size is not None:
            zones[size].add(placement.cut_zone)
    if any(len(values) > 1 for values in zones.values()):
        raise ValueError('同尺码单件被拆到不同旋转区域，禁止输出。')
    sequence = list(zones)
    if sequence != sorted(sequence, key=size_key):
        raise ValueError('单件尺码未按从小到大排列，禁止输出。')
    return {'single_size_blocks': sequence, 'single_size_verified': True}
