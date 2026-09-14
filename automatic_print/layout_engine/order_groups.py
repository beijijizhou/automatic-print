"""Production identity is independent of the per-image export sequence prefix."""
from collections import OrderedDict
import re
from functools import lru_cache

PREFIX = re.compile(r"^(?:CVC面料\d+-|A\d+-(?!\d+-))", re.I)
SIDE = re.compile(r"^(?P<job>.+-NO\d+)-(?P<side>[12])$", re.I)


def production_stem(path):
    return PREFIX.sub("", path.stem, count=1).casefold()


@lru_cache(maxsize=4096)
def order_key(path):
    stem = production_stem(path)
    return stem.split("-", 1)[0] if "-" in stem else "未识别订单组"


@lru_cache(maxsize=4096)
def pair_identity(path):
    match = SIDE.fullmatch(production_stem(path))
    return (match['job'], match['side']) if match else None


def is_double_pair(first, second):
    one, two = pair_identity(first), pair_identity(second)
    return bool(one and two and one[0] == two[0] and {one[1], two[1]} == {'1', '2'})


def complete_orders(paths):
    groups = OrderedDict()
    for path in paths:
        groups.setdefault(order_key(path), []).append(path)
    return list(groups.values())


def _size_rank(size):
    named = {'xxs': 10, 'xs': 20, 's': 30, 'm': 40, 'l': 50}
    if size in named:
        return named[size]
    match = re.fullmatch(r'(\d*)xl', size)
    if match:
        return 50 + 10 * int(match[1] or 1)
    match = re.fullmatch(r'(x+)l', size)
    if match:
        return 50 + 10 * len(match[1])
    return 1000


def _piece_sort(path):
    stem = production_stem(path)
    parts = stem.split('-')
    # The size directly precedes NO; item/export ordinals must not sort before size.
    if len(parts) >= 5 and re.fullmatch(r'no\d+', parts[-2]):
        from .source_metadata import source_color, color_key
        item = int(parts[1]) if parts[1].isdigit() else 0
        return color_key(source_color(path)), _size_rank(parts[-3]), parts[-3], tuple(parts[2:-3]), item, parts[-2], parts[-1]
    return (3,'未识别颜色'), 1000, '', (stem,), 0, '', ''


def ordered_paths(paths):
    ordered = []
    for group in complete_orders(paths):
        if order_key(group[0]) != '未识别订单组':
            group = sorted(group, key=_piece_sort)
        # Gather both sides even if source directories or export ordinals differ.
        pieces = OrderedDict()
        for path in group:
            identity = pair_identity(path)
            key = ('pair', identity[0]) if identity else ('single', path)
            pieces.setdefault(key, []).append(path)
        for members in pieces.values():
            if pair_identity(members[0]):
                sides = [pair_identity(p)[1] for p in members]
                if len(sides) != len(set(sides)):
                    raise ValueError(f"同件商品存在重复面，无法可靠归组：{members[0].name}")
                members.sort(key=lambda p: pair_identity(p)[1])
            ordered.extend(members)
    from .size_policy import ordered_single_blocks
    return [path for group in ordered_single_blocks(complete_orders(ordered)) for path in group]


def detail_members(planned, selected=None, index=0):
    """Select the real product pair, never a slice of unrelated source filenames."""
    if not planned:
        return []
    selected = selected if any(p == selected for p, _ in planned) else planned[min(index, len(planned)-1)][0]
    identity = pair_identity(selected)
    if identity:
        members = [(path, p) for path, p in planned if pair_identity(path) and pair_identity(path)[0] == identity[0]]
        if len(members) == 2:
            return members
    position = next(i for i, (path, _) in enumerate(planned) if path == selected)
    row = planned[position][1].row_y_px
    zone = planned[position][1].cut_zone
    return [(path, p) for path, p in planned if p.row_y_px == row and p.cut_zone == zone]
