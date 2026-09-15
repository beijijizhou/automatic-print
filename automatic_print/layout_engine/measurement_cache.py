"""Persistent per-file geometry facts, independent from whole-batch plans."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from threading import RLock
from time import time


ITEM_SCHEMA = 1
DIMENSION_SCHEMA = 2
TTL_SECONDS = 24 * 60 * 60


def cache_directory():
    from ..crash_logging import log_folder
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
        return json.loads(row[0]) if row else None

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
    return MeasurementCache.key(ITEM_SCHEMA, (
        file_identity, index, width, height, asdict(settings), degrees, date,
    ))


def dimension_key(file_identity, fallback_dpi):
    return MeasurementCache.key(
        DIMENSION_SCHEMA, (file_identity, fallback_dpi)
    )


def encode_item(item, text):
    value = asdict(item)
    value['path'] = str(item.path)
    return {'item': value, 'text': text}


def decode_item(value):
    from .item_factory import LayoutItem
    data = value['item']
    data['path'] = Path(data['path'])
    return LayoutItem(**data), value.get('text')
