"""Persistent per-file geometry facts, independent from whole-batch plans."""
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from threading import RLock
from time import time


ITEM_SCHEMA = 2
DIMENSION_SCHEMA = 2
TRANSPARENT_RECT_SCHEMA = 1
HEADER_REGION_SCHEMA = 1
TTL_SECONDS = 24 * 60 * 60


class UnavailableMeasurementCache:
    """No-op batch fallback after the persistent cache fails once."""

    def load(self, _kind, _key):
        return None

    def load_many(self, _kind, _keys):
        return {}

    def save(self, _kind, _key, _value):
        return None

    def close(self):
        return None


def cache_directory():
    from automatic_print.runtime.crash_logging import log_folder
    return log_folder()


class MeasurementCache:
    """One thread-safe connection shared by a batch measurement session."""

    def __init__(self):
        directory = cache_directory()
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.connection = sqlite3.connect(
            directory / '图片测量缓存.sqlite3', timeout=15,
            check_same_thread=False,
        )
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute(
            'CREATE TABLE IF NOT EXISTS measurements '
            '(kind TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL, '
            'updated REAL NOT NULL, PRIMARY KEY(kind, key))'
        )
        with self.connection:
            self.connection.execute(
                'DELETE FROM measurements WHERE updated <= ?',
                (time() - TTL_SECONDS,),
            )

    @staticmethod
    def key(schema, values):
        payload = json.dumps(
            {'schema': schema, 'values': values},
            sort_keys=True, ensure_ascii=False, default=str,
        )
        return sha256(payload.encode()).hexdigest()

    def load(self, kind, key):
        with self.lock:
            row = self.connection.execute(
                'SELECT payload FROM measurements '
                'WHERE kind=? AND key=? AND updated>?',
                (kind, key, time() - TTL_SECONDS),
            ).fetchone()
            payload = row[0] if row else None
        return json.loads(payload) if payload else None

    def load_many(self, kind, keys):
        keys = tuple(dict.fromkeys(keys))
        result = {}
        with self.lock:
            for start in range(0, len(keys), 500):
                chunk = keys[start:start + 500]
                marks = ','.join('?' for _ in chunk)
                rows = self.connection.execute(
                    f'SELECT key, payload FROM measurements WHERE kind=? '
                    f'AND updated>? AND key IN ({marks})',
                    (kind, time() - TTL_SECONDS, *chunk),
                )
                result.update((key, json.loads(payload))
                              for key, payload in rows)
        return result

    def save(self, kind, key, value):
        payload = json.dumps(value, ensure_ascii=False, default=str)
        with self.lock, self.connection:
            self.connection.execute(
                'INSERT OR REPLACE INTO measurements VALUES (?, ?, ?, ?)',
                (kind, key, payload, time()),
            )

    def close(self):
        with self.lock:
            self.connection.close()


def item_key(file_identity, index, width, height, settings, degrees, created_at):
    template = settings.label_text_template
    date = created_at.strftime(settings.label_date_format) if (
        '{日期}' in template or '{date' in template
    ) else ''
    settings_data = asdict(settings)
    # This switch changes only whole-batch packing.  Keeping it out of the
    # per-image geometry key preserves measurements made by earlier releases
    # and avoids decoding every source again when developer mode changes.
    settings_data.pop('developer_compact_cutter_layout', None)
    return MeasurementCache.key(ITEM_SCHEMA, (
        file_identity, index, width, height, settings_data, degrees, date,
    ))


def item_settings(settings):
    """Keep only fields that affect one source image's cached geometry."""
    return replace(
        settings, media_width_mm=600,
        label_batch_name=(settings.label_batch_name
                          if settings.label_source_order_enabled else ''),
        worker_threads=1, output_parts=1,
        cutter_mode='free' if settings.cutter_mode == 'free' else 'dual',
        save_parallelism=1, save_memory_mb=512, save_memory_unlimited=False,
        output_format='png', png_engine='pillow', png_compression_level=1,
        png_fast_encoding=False, png_streaming=False,
        compare_film_sizes=False, compare_reference_films=False,
        film_geometry_workers=4, cutter_auto_knife=False,
        cutter_rotation_zone=False, cutter_tail_rotation=False,
        cutter_majority_two_zone=False, force_small_pair_width=False,
        force_small_pair_width_mm=270, dimension_overrides=(), header_gap_overrides=(),
        width_adjustments=(), cutter_knife_mm=300, cutter_safety_mm=3,
        cutter_marker_offset_mm=0, allow_rotation=False, manual_rotations=(),
        sequence_numbers=(), riin_left_mm=10, riin_right_mm=10,
    )


def dimension_key(file_identity, fallback_dpi):
    return MeasurementCache.key(
        DIMENSION_SCHEMA, (file_identity, fallback_dpi)
    )


def transparent_rect_key(
    file_identity, width, height, degrees, rectangle,
):
    return MeasurementCache.key(
        TRANSPARENT_RECT_SCHEMA,
        (file_identity, width, height, degrees, tuple(rectangle)),
    )


def header_region_key(file_identity):
    return MeasurementCache.key(HEADER_REGION_SCHEMA, file_identity)


def encode_item(item, text):
    value = asdict(item)
    value['path'] = str(item.path)
    return {'item': value, 'text': text}


def decode_item(value):
    from automatic_print.layout_engine.domain.models import LayoutItem
    data = value['item']
    data['path'] = Path(data['path'])
    return LayoutItem(**data), value.get('text')
