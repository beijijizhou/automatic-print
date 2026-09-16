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
    with session.identity_lock:
        cached = session.cutter_batches.get(_key(paths, settings))
    if cached is None:
        return None
    choices, labels = cached
    return choices, dict(labels)


def store_cutter_measurements(paths, settings, choices, labels):
    session = SESSION.get()
    if session is None:
        return
    with session.identity_lock:
        session.cutter_batches[_key(paths, settings)] = choices, dict(labels)
