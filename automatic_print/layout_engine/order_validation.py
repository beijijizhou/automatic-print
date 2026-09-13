"""Independently reject lost, interleaved or cross-zone order/pair placements."""
from collections import Counter, defaultdict

from .order_groups import order_key, pair_identity
from .size_policy import validate_single_size_blocks


def validate_order_placements(paths, planned):
    if Counter(paths) != Counter(path for path, _ in planned):
        raise ValueError('排版丢失或重复了源图片，禁止输出。')
    orders, pairs = defaultdict(list), defaultdict(list)
    for index, (path, placement) in enumerate(planned):
        orders[order_key(path)].append((index, placement))
        identity = pair_identity(path)
        if identity:
            pairs[identity[0]].append((index, placement, identity[1]))
    for key, entries in orders.items():
        positions = [i for i, _ in entries]
        if positions[-1]-positions[0]+1 != len(positions):
            raise ValueError(f'订单 {key} 被其他订单插入，禁止输出。')
        if len({p.cut_zone for _, p in entries}) != 1:
            raise ValueError(f'订单 {key} 被拆到不同区域，禁止输出。')
    horizontal, vertical = 0, 0
    for key, entries in pairs.items():
        sides = [side for _, _, side in entries]
        if len(sides) != len(set(sides)):
            raise ValueError(f'商品 {key} 存在重复面，禁止输出。')
        if len(entries) != 2:
            continue
        (a, first, _), (b, second, _) = entries
        if b != a+1:
            raise ValueError(f'双面 {key} 不相邻，禁止输出。')
        if first.y_px == second.y_px and first.cut_zone != '旋转区':
            horizontal += 1
        else:
            if not (first.y_px+first.height_px <= second.y_px or
                    second.y_px+second.height_px <= first.y_px):
                raise ValueError(f'双面 {key} 错位且存在高度重叠，禁止输出。')
            vertical += 1
    size_check = validate_single_size_blocks(paths, planned)
    return {**size_check, 'orders': len(orders), 'double_pairs': horizontal+vertical,
            'horizontal_pairs': horizontal, 'vertical_pairs': vertical}
