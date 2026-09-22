"""Match gateway records to local S2B images without rereading image pixels."""
from collections import defaultdict
from pathlib import Path
import re
from threading import RLock

from .batch_name import find_s2b_batch_folder, parse_s2b_image_name


_LOCK = RLock()
_COLORS = {}
_ORDERS = {}
_BATCHES = {}


def _identity(path):
    path = path.resolve()
    try:
        stat = path.stat()
    except OSError:
        return str(path), None, None
    return str(path), stat.st_mtime_ns, stat.st_size


def _cached(mapping, path):
    key = str(path.resolve())
    identity = _identity(path)
    with _LOCK:
        entry = mapping.get(key)
        if entry and entry[0] == identity:
            return entry[1]
        mapping.pop(key, None)
    return None


def _contains_code(folder_name, code):
    code = str(code or "").strip().casefold()
    return bool(code and re.search(
        rf"(?<![a-z0-9]){re.escape(code)}(?![a-z0-9])",
        folder_name.casefold(),
    ))


def _folder_candidates(path, records):
    batch = find_s2b_batch_folder(path)
    if not batch:
        return []
    folders = []
    current = path.parent
    while current != batch.path and batch.path in current.parents:
        folders.append(current.name)
        current = current.parent
    for field in ("order_item_code", "order_code"):
        matched = [
            record for record in records
            if any(_contains_code(folder, record.get(field)) for folder in folders)
        ]
        orders = {
            str(record.get("order_code") or "").strip().casefold()
            for record in matched
        }
        orders.discard("")
        if len(orders) == 1:
            return matched
    return []


def register_batch_records(paths, payload):
    from .....layout_engine.orders.order_groups import order_key, production_stem
    from .....layout_engine.intake.metadata.source_metadata import canonical_size, source_size

    by_order = defaultdict(list)
    for record in payload.get("records") or ():
        order = str(record.get("order_code") or "").strip().casefold()
        if order:
            by_order[order].append(record)
    resolved = {}
    resolved_orders = {}
    records = list(payload.get("records") or ())
    for path in paths:
        image = parse_s2b_image_name(path)
        if image:
            if image.batch_number != str(payload.get("batch_number") or "").upper():
                continue
            candidates = [
                row for row in by_order.get(image.order_code.casefold(), ())
                if str(row.get("order_item_code") or "").casefold()
                == image.order_item_code.casefold()
                and canonical_size(str(row.get("size") or ""))
                == canonical_size(image.size)
            ]
        else:
            candidates = by_order.get(order_key(path).casefold(), ())
            if not candidates:
                candidates = _folder_candidates(path, records)
        if not candidates:
            continue
        orders = {
            str(row.get("order_code") or "").strip()
            for row in candidates
        }
        orders.discard("")
        if len(orders) == 1:
            resolved_orders[str(path.resolve())] = (_identity(path), next(iter(orders)))
        if not image:
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
            resolved[str(path.resolve())] = (_identity(path), next(iter(colors)))
    batch = str(payload.get("batch_number") or "")
    with _LOCK:
        _COLORS.update(resolved)
        _ORDERS.update(resolved_orders)
        if batch:
            _BATCHES[batch] = {
                "source_total": payload.get("source_total"),
                "summary": payload.get("summary") or {},
                "cache": payload.get("cache") or "",
                "matched_images": len(resolved),
            }
    from .....layout_engine.intake.metadata.source_metadata import source_color
    source_color.cache_clear()
    order_key.cache_clear()
    return len(resolved)


def color_for_path(path):
    return _cached(_COLORS, path)


def order_for_path(path):
    return _cached(_ORDERS, path)


def batch_metadata(batch_number):
    with _LOCK:
        return dict(_BATCHES.get(str(batch_number), {}))


def register_path_aliases(path_mapping):
    """Carry API identity onto lossless prepared copies used by layout."""
    aliases = []
    for source, prepared in path_mapping.items():
        source = Path(source)
        prepared = Path(prepared)
        color = color_for_path(source)
        order = order_for_path(source)
        identity = _identity(prepared)
        aliases.append((str(prepared.resolve()), identity, color, order))
    with _LOCK:
        for path, identity, color, order in aliases:
            if color:
                _COLORS[path] = (identity, color)
            if order:
                _ORDERS[path] = (identity, order)
    from .....layout_engine.intake.metadata.source_metadata import source_color
    from .....layout_engine.orders.order_groups import order_key
    source_color.cache_clear()
    order_key.cache_clear()
