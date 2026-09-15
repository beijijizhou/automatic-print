"""Batch-scoped immutable measurement results; never cache whole-batch pixels."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from dataclasses import replace
from PIL import Image
from threading import RLock
from concurrent.futures import Future
import sqlite3

SESSION = ContextVar('layout_measurements', default=None)
SOURCE = ContextVar('layout_measurement_source', default=None)


class Measurements:
    def __init__(self):
        self.created_at = datetime.now().astimezone()
        self.items, self.dimensions, self.rectangles = {}, {}, {}
        self.bands = {}
        self.identities, self.identity_lock = {}, RLock()
        self.persistent = None
        self.persistent_lock = RLock()
        from .measurement_timing import MeasurementTiming
        self.timing = MeasurementTiming()


@contextmanager
def measurement_session():
    if SESSION.get() is not None:
        yield SESSION.get()
        return
    token = SESSION.set(Measurements())
    try:
        yield SESSION.get()
    finally:
        session = SESSION.get()
        if session.persistent is not None:
            try:
                session.persistent.close()
            except sqlite3.Error:
                pass
        SESSION.reset(token)


def persistent_cache():
    session = SESSION.get()
    if session is None:
        return None
    with session.persistent_lock:
        if session.persistent is None:
            from .measurement_cache import MeasurementCache
            session.persistent = MeasurementCache()
        return session.persistent


def identity(path):
    session = SESSION.get()
    if session is not None:
        with session.identity_lock:
            leader = path not in session.identities
            future = session.identities.setdefault(path, Future())
        if leader:
            try:
                future.set_result(fresh_identity(path))
            except BaseException as exc:
                future.set_exception(exc)
                raise
        return future.result()
    return fresh_identity(path)


def fresh_identity(path):
    stat = path.stat()
    return str(path.resolve()), stat.st_mtime_ns, stat.st_size


def resolved_name(path):
    session = SESSION.get()
    if session is not None and path in session.identities:
        return session.identities[path].result()[0]
    return str(path.resolve())


def verify_sources():
    session = SESSION.get()
    if session is not None:
        for path, expected in session.identities.items():
            if fresh_identity(path) != expected.result():
                raise ValueError(f'{path.name}：源文件在排版计算期间发生变化，请重新生成。')


def item_settings(settings):
    # These fields do not affect the pixels or geometry of an individual item.
    return replace(settings, media_width_mm=600, worker_threads=1, output_parts=1,
                   cutter_mode='free' if settings.cutter_mode == 'free' else 'dual',
                   save_parallelism=1, save_memory_mb=512, save_memory_unlimited=False,
                   compare_film_sizes=False, compare_reference_films=False, film_geometry_workers=4,
                   cutter_auto_knife=False,
                   cutter_rotation_zone=False, cutter_tail_rotation=False,
                   cutter_majority_two_zone=False,
                   cutter_knife_mm=300, cutter_safety_mm=3, cutter_marker_offset_mm=0,
                   allow_rotation=False, manual_rotations=(), sequence_numbers=(),
                   riin_left_mm=10, riin_right_mm=10)


def active_source(path):
    current = SOURCE.get()
    return current[1] if current is not None and current[0] == path else None


@contextmanager
def source_pixels(path):
    from .measurement_timing import decode_source
    source = active_source(path)
    if source is not None:
        yield decode_source(source) if 'A' in source.getbands() else source
        return
    with Image.open(path) as source:
        yield decode_source(source) if 'A' in source.getbands() else source


@contextmanager
def measuring_source(path):
    if active_source(path) is not None:
        yield
        return
    with Image.open(path) as source:
        token = SOURCE.set((path, source))
        try:
            yield
        finally:
            SOURCE.reset(token)


def measured_item(make, path, index, width, height, settings, labels, created_at,
                   gap, offset_x, offset_y, rotation_degrees, qr_location):
    session = SESSION.get()
    key = (identity(path), index, width, height, item_settings(settings), rotation_degrees) if session else None
    if session and key in session.items:
        item, text = session.items[key]
        if text is not None:
            labels[index] = text
        return item
    persistent, persistent_key = None, None
    if session:
        try:
            from .measurement_cache import item_key, decode_item
            persistent = persistent_cache()
            persistent_key = item_key(
                key[0], index, width, height, key[4], rotation_degrees,
                created_at,
            )
            cached = persistent.load('item', persistent_key)
            if cached is not None:
                item, text = decode_item(cached)
                session.items[key] = item, text
                session.timing.cache_item(True)
                if text is not None:
                    labels[index] = text
                return item
            session.timing.cache_item(False)
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            persistent = persistent_key = None
    with measuring_source(path):
        item = make(path, index, width, height, settings, labels, created_at,
                    gap, offset_x, offset_y, rotation_degrees, qr_location)
    if session:
        session.items[key] = item, labels.get(index)
        if persistent is not None and persistent_key is not None:
            try:
                from .measurement_cache import encode_item
                persistent.save('item', persistent_key, encode_item(item, labels.get(index)))
            except (OSError, ValueError, TypeError, sqlite3.Error):
                pass
    return item


@contextmanager
def choice_source(path, index, width, height, settings, manual):
    session = SESSION.get()
    sizes = [(width, height, manual)]
    if settings.allow_rotation and not manual and width != height:
        sizes.append((height, width, 90 if settings.rotation_direction == 'left' else -90))
    if session:
        file_key, normalized = identity(path), item_settings(settings)
        keys = [(file_key, index, w, h, normalized, degrees)
                for w, h, degrees in sizes]
        if all(key in session.items for key in keys):
            yield
            return
        try:
            from .measurement_cache import item_key, decode_item
            persistent = persistent_cache()
            cached = []
            for key, (_width, _height, degrees) in zip(keys, sizes, strict=True):
                value = persistent.load('item', item_key(
                    file_key, index, key[2], key[3], normalized, degrees,
                    session.created_at,
                ))
                if value is None:
                    break
                cached.append((key, decode_item(value)))
            if len(cached) == len(keys):
                session.items.update(cached)
                for _ in cached:
                    session.timing.cache_item(True)
                yield
                return
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            pass
    with measuring_source(path):
        yield
