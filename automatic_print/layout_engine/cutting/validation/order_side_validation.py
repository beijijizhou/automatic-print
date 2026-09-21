"""Production order checks for the explicitly enabled whole-order side mode."""
from collections import Counter, defaultdict

from automatic_print.layout_engine.orders.order_groups import order_key
from .order_validation import validate_order_placements


def validate_order_side_placements(paths, planned, knife_x):
    if Counter(paths) != Counter(path for path, _placement in planned):
        raise ValueError('整单归侧排版丢失或重复源图片，禁止输出。')
    zones = defaultdict(list)
    order_zones = defaultdict(set)
    for path, placement in planned:
        zones[placement.cut_zone].append((path, placement))
        order_zones[order_key(path)].add(placement.cut_zone)
    if set(zones) - {'并排区', '旋转区'}:
        raise ValueError('整单归侧排版出现未知区域，禁止输出。')
    if any(len(members) != 1 for members in order_zones.values()):
        raise ValueError('同一订单跨越常规与旋转区域，禁止输出。')

    normal = zones['并排区']
    sides = defaultdict(set)
    checks = []
    for lane in (0, 1):
        members = [(path, placement) for path, placement in normal
                   if (placement.x_px < knife_x) == (lane == 0)]
        if not members:
            continue
        members.sort(key=lambda entry: (entry[1].row_y_px, entry[1].x_px))
        for path, placement in members:
            sides[order_key(path)].add(lane)
            if placement.cut_knife_xs_px != (knife_x,):
                raise ValueError('常规区含非共用刀位，禁止输出。')
        checks.append(validate_order_placements(
            [path for path, _placement in members], members))
    if any(len(lanes) != 1 for lanes in sides.values()):
        raise ValueError('同一订单跨越左右固定刀位，禁止输出。')
    rotated = zones['旋转区']
    if rotated:
        rotated.sort(key=lambda entry: (entry[1].row_y_px, entry[1].x_px))
        checks.append(validate_order_placements(
            [path for path, _placement in rotated], rotated))
        if normal and min(p.row_y_px for _path, p in rotated) < max(
                p.row_y_px + p.footprint_height_px for _path, p in normal):
            raise ValueError('旋转区与常规区纵向重叠，禁止输出。')
    return {'orders': len(order_zones),
            'double_pairs': sum(check['double_pairs'] for check in checks),
            'horizontal_pairs': sum(check['horizontal_pairs'] for check in checks),
            'vertical_pairs': sum(check['vertical_pairs'] for check in checks),
            'single_size_blocks': list(dict.fromkeys(
                size for check in checks for size in check['single_size_blocks'])),
            'single_color_size_blocks': [
                {'color': color, 'size': size} for color, size in dict.fromkeys(
                    (entry['color'], entry['size']) for check in checks
                    for entry in check['single_color_size_blocks'])],
            'single_size_verified': True}
