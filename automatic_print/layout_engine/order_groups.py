"""Production identity is independent of the per-image export sequence prefix."""
from collections import defaultdict, OrderedDict
import re
from functools import lru_cache
from threading import RLock

PREFIX = re.compile(r"^(?:(?:[A-Z]+-)?CVC面料\d+-|A\d+-(?!\d+-))", re.I)
S2B_PREFIX = re.compile(r"^[A-Z0-9]+-\d+-\d+-", re.I)
SIZE_FOLDER = re.compile(r"^(?:XXS|XS|S|M|L|XL|XXL|[2-9]XL)$", re.I)
SIDE = re.compile(r"^(?P<job>.+-NO\d+)-(?P<side>[12])$", re.I)
S2B_SIDE = re.compile(
    r"^(?P<batch>[A-Z0-9]{12})-(?P<item>\d+)-\d+-"
    r"(?P<order>[A-Z0-9]+)-(?P<side>[12])-2-(?P<unit>\d+)-\d+-"
    r".+-(?P<size>XXS|XS|S|M|L|XL|XXL|[2-9]XL)$",
    re.I,
)
_S2B_PAIR_LOCK = RLock()
_S2B_PAIRS = {}


def production_stem(path):
    stem = PREFIX.sub("", path.stem, count=1)
    if SIZE_FOLDER.fullmatch(path.parent.name.strip()):
        stem = S2B_PREFIX.sub("", stem, count=1)
    return stem.casefold()


@lru_cache(maxsize=4096)
def order_key(path):
    from ..automation.api.s2b.metadata import order_for_path
    api_order = order_for_path(path)
    if api_order:
        return api_order.casefold()
    stem = production_stem(path)
    return stem.split("-", 1)[0] if "-" in stem else "未识别订单组"


@lru_cache(maxsize=4096)
def pair_identity(path):
    match = SIDE.fullmatch(production_stem(path))
    if match:
        return match['job'], match['side']
    with _S2B_PAIR_LOCK:
        return _S2B_PAIRS.get(str(path.resolve()))


def register_s2b_pairs(paths):
    """Register only complete same-product, same-size 1/2 + 2/2 pairs."""
    groups = defaultdict(list)
    resolved_paths = [str(path.resolve()) for path in paths]
    for path in paths:
        match = S2B_SIDE.fullmatch(path.stem)
        if not match:
            continue
        job = ":".join((
            "s2b", match['batch'], match['item'], match['order'],
            match['unit'], match['size'],
        )).casefold()
        groups[job].append((path, match['side']))
    registered = {}
    for job, members in groups.items():
        if len(members) == 2 and {side for _, side in members} == {'1', '2'}:
            registered.update(
                (str(path.resolve()), (job, side)) for path, side in members
            )
    with _S2B_PAIR_LOCK:
        for path in resolved_paths:
            _S2B_PAIRS.pop(path, None)
        _S2B_PAIRS.update(registered)
    pair_identity.cache_clear()
    return len(registered) // 2


def is_double_pair(first, second):
    one, two = pair_identity(first), pair_identity(second)
    return bool(one and two and one[0] == two[0] and {one[1], two[1]} == {'1', '2'})


def complete_orders(paths):
    register_s2b_pairs(paths)
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
