"""Match gateway records to local S2B images without rereading image pixels."""
from collections import defaultdict
from threading import RLock


_LOCK = RLock()
_COLORS = {}
_BATCHES = {}


def register_batch_records(paths, payload):
    from ....layout_engine.order_groups import order_key, production_stem
    from ....layout_engine.source_metadata import canonical_size, source_size

    by_order = defaultdict(list)
    for record in payload.get("records") or ():
        order = str(record.get("order_code") or "").strip().casefold()
        if order:
            by_order[order].append(record)
    resolved = {}
    for path in paths:
        candidates = by_order.get(order_key(path).casefold(), ())
        if not candidates:
            continue
        stem = production_stem(path)
        exact = [row for row in candidates if stem.startswith(
            str(row.get("order_item_code") or "").strip().casefold() + "-"
        )]
        candidates = exact or list(candidates)
        size = canonical_size(source_size(path))
        same_size = [row for row in candidates if canonical_size(
            str(row.get("size") or "")
        ) == size]
        candidates = same_size or candidates
        colors = {str(row.get("color") or "").strip() for row in candidates}
        colors.discard("")
        if len(colors) == 1:
            resolved[str(path.resolve())] = next(iter(colors))
    batch = str(payload.get("batch_number") or "")
    with _LOCK:
        _COLORS.update(resolved)
        if batch:
            _BATCHES[batch] = {
                "source_total": payload.get("source_total"),
                "summary": payload.get("summary") or {},
                "cache": payload.get("cache") or "",
                "matched_images": len(resolved),
            }
    from ....layout_engine.source_metadata import source_color
    source_color.cache_clear()
    return len(resolved)


def color_for_path(path):
    with _LOCK:
        return _COLORS.get(str(path.resolve()))


def batch_metadata(batch_number):
    with _LOCK:
        return dict(_BATCHES.get(str(batch_number), {}))
