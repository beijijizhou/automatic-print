"""Single-piece size blocks are production constraints, not packing hints."""
from collections import defaultdict
from automatic_print.layout_engine.orders.order_groups import order_key, pair_identity
from automatic_print.layout_engine.intake.metadata.source_metadata import source_size, size_key, source_color, source_block, block_key


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
            sizes[source_block(order[0])].append(order)
    result = list(locked)
    for size in sorted(sizes, key=block_key):
        members = sizes[size]
        result.extend([[path for order in members for path in order]] if coalesce else members)
    from .color_policy import order_color_key
    return sorted(result,key=order_color_key)


def same_single_size(first, second):
    if source_color(first) != source_color(second):
        return False
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
    eligible = {path: source_block(path) for order in complete_orders(paths)
                if (size := single_order_size(order)) is not None for path in order}
    ordered = sorted(planned, key=lambda entry: (entry[1].row_y_px, entry[1].x_px))
    zones = {placement.cut_zone for _path, placement in ordered}
    groups = ({zone: [(path, p) for path, p in ordered if p.cut_zone == zone]
               for zone in ('并排区', '旋转区')} if zones == {'并排区', '旋转区'}
              else {'整批': ordered})
    sequences = []
    for zone, entries in groups.items():
        sequence = []
        for path, _placement in entries:
            block = eligible.get(path)
            if block is not None and (not sequence or sequence[-1] != block):
                sequence.append(block)
        if sequence != sorted(sequence, key=block_key):
            raise ValueError(f'{zone}内单件未按颜色优先、同色尺码从小到大排列，禁止输出。')
        sequences.extend(sequence)
    sequence = list(dict.fromkeys(sequences))
    return {'single_size_blocks': [size for _,size in sequence], 'single_size_verified': True,
            'single_color_size_blocks': [{'color':color,'size':size} for color,size in sequence]}
