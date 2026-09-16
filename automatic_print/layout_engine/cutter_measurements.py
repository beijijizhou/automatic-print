"""Batch-scoped cutter geometry reused by production and film comparisons."""
from .measurement_session import SESSION, identity, resolved_name
from .measurement_cache import item_settings


def _key(paths, settings):
    numbers = dict(settings.sequence_numbers)
    rotations = dict(settings.manual_rotations)
    overrides = dict(settings.dimension_overrides)
    return (
        tuple(
            (
                identity(path),
                numbers.get(resolved_name(path), index),
                rotations.get(resolved_name(path), 0),
                overrides.get(resolved_name(path)),
            )
            for index, path in enumerate(paths, 1)
        ),
        item_settings(settings),
        bool(settings.allow_rotation),
    )


def load_cutter_measurements(paths, settings):
    session = SESSION.get()
    if session is None:
        return None
    key = _key(paths, settings)
    with session.identity_lock:
        cached = session.cutter_batches.get(key)
        if cached is None:
            cached = _same_batch_in_new_order(session.cutter_batches, key)
    if cached is None:
        return None
    choices, labels = cached
    return choices, dict(labels)


def _same_batch_in_new_order(cached_batches, requested_key):
    """Reuse one measured batch after a planner changes only its path order."""
    requested_files, requested_settings, requested_rotation = requested_key
    requested_by_identity = {row[0]: row for row in requested_files}
    for (stored_files, stored_settings, stored_rotation), value in cached_batches.items():
        if (
            stored_settings != requested_settings
            or stored_rotation != requested_rotation
            or len(stored_files) != len(requested_files)
        ):
            continue
        stored_by_identity = {row[0]: row for row in stored_files}
        if stored_by_identity != requested_by_identity:
            continue
        choices, labels = value
        choices_by_path = {str(row[0].path.resolve()): row for row in choices}
        requested_paths = tuple(entry[0][0] for entry in requested_files)
        if all(path in choices_by_path for path in requested_paths):
            ordered = tuple(choices_by_path[path] for path in requested_paths)
            return ordered, labels
    return None


def store_cutter_measurements(paths, settings, choices, labels):
    session = SESSION.get()
    if session is None:
        return
    with session.identity_lock:
        session.cutter_batches[_key(paths, settings)] = choices, dict(labels)
