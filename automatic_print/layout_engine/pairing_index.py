"""Exact greedy partner selection over equivalent geometry buckets."""
from collections import defaultdict, deque


def indexed_sequence(orders, items, lanes, prepared):
    from .single_order_sequence import lane_fits, horizontal_savings
    locked, pending, sizes = prepared
    fits = {path: tuple(lane_fits(item, lane) for lane in lanes) for path, item in items.items()}
    buckets = defaultdict(dict)
    for index in pending:
        if len(orders[index]) != 1:
            continue
        b = items[orders[index][0]]
        key = b.footprint_height, b.image_ry, b.rotation_degrees, fits[b.path]
        buckets[sizes[index]].setdefault(key, deque()).append(index)
    rank = {index: pos for pos, index in enumerate(pending)}
    active, ordered = set(pending), list(locked)
    for first in pending:
        if first not in active:
            continue
        active.remove(first)
        ordered.append(first)
        if len(orders[first]) != 1:
            continue
        a, best = items[orders[first][0]], None
        for bucket in buckets[sizes[first]].values():
            while bucket and bucket[0] not in active:
                bucket.popleft()
            if not bucket:
                continue
            index = bucket[0]
            saved = horizontal_savings(a, items[orders[index][0]], lanes, fits)
            if saved is not None and saved > 0:
                candidate = -saved, rank[index], index
                if best is None or candidate < best:
                    best = candidate
        if best is not None:
            partner = best[-1]
            active.remove(partner)
            ordered.append(partner)
    return ordered
