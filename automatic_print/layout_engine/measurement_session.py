"""Batch-scoped immutable measurement results; never cache whole-batch pixels."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from dataclasses import replace
from PIL import Image

SESSION = ContextVar('layout_measurements', default=None)
SOURCE = ContextVar('layout_measurement_source', default=None)


class Measurements:
    def __init__(self):
        self.created_at = datetime.now().astimezone()
        self.items, self.dimensions, self.rectangles = {}, {}, {}


@contextmanager
def measurement_session():
    if SESSION.get() is not None:
        yield SESSION.get()
        return
    token = SESSION.set(Measurements())
    try:
        yield SESSION.get()
    finally:
        SESSION.reset(token)


def identity(path):
    stat = path.stat()
    return str(path.resolve()), stat.st_mtime_ns, stat.st_size


def item_settings(settings):
    # These fields do not affect the pixels or geometry of an individual item.
    return replace(settings, media_width_mm=600, worker_threads=1, output_parts=1,
                   cutter_mode='free' if settings.cutter_mode == 'free' else 'dual',
                   save_parallelism=1, save_memory_mb=512, save_memory_unlimited=False,
                   compare_film_sizes=False, compare_reference_films=False, cutter_auto_knife=False,
                   cutter_rotation_zone=False, cutter_tail_rotation=False,
                   cutter_knife_mm=300, cutter_safety_mm=3, cutter_marker_offset_mm=0,
                   allow_rotation=False, manual_rotations=(), sequence_numbers=(),
                   riin_left_mm=10, riin_right_mm=10)


def active_source(path):
    current = SOURCE.get()
    return current[1] if current is not None and current[0] == path else None


@contextmanager
def source_pixels(path):
    source = active_source(path)
    if source is not None:
        yield source
        return
    with Image.open(path) as source:
        yield source


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
    with measuring_source(path):
        item = make(path, index, width, height, settings, labels, created_at,
                    gap, offset_x, offset_y, rotation_degrees, qr_location)
    if session:
        session.items[key] = item, labels.get(index)
    return item


@contextmanager
def choice_source(path, index, width, height, settings, manual):
    session = SESSION.get()
    sizes = [(width, height, manual)]
    if settings.allow_rotation and not manual and width != height:
        sizes.append((height, width, 90 if settings.rotation_direction == 'left' else -90))
    if session:
        file_key, normalized = identity(path), item_settings(settings)
        if all((file_key, index, w, h, normalized, degrees) in session.items
               for w, h, degrees in sizes):
            yield
            return
    with measuring_source(path):
        yield
