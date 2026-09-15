"""Persistent JSON-only geometry cache; source/output safety remains independent."""
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from time import time

from .measurement_session import identity
from .models import Placement

SCHEMA = 1
TTL_SECONDS = 24 * 60 * 60


def cache_directory():
    from ..crash_logging import log_folder
    return log_folder()


def cache_key(paths, settings, created_at, progress=None):
    from .. import __version__
    template = settings.label_text_template
    date = created_at.strftime(settings.label_date_format) if ('{日期}' in template or '{date' in template) else ''
    settings = replace(settings, worker_threads=1, output_parts=1, save_parallelism=1,
                       save_memory_mb=512, save_memory_unlimited=False, png_engine='pillow',
                       png_compression_level=1, png_fast_encoding=False, png_streaming=False, film_geometry_workers=1)
    files = []
    for index, path in enumerate(paths, 1):
        files.append(identity(path))
        if progress:
            progress('读取排版缓存', index, len(paths), '检查文件信息：'+path.name)
    data = {'schema': SCHEMA, 'algorithm': __version__, 'files': files,
            'settings': asdict(settings), 'date': date}
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def connect():
    directory = cache_directory()
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(directory/'排版缓存.sqlite3', timeout=15)
    try:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE IF NOT EXISTS plans '
                           '(key TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL, updated REAL NOT NULL)')
        connection.execute('CREATE INDEX IF NOT EXISTS plans_updated ON plans(updated)')
        # Absolute lifetime from save, not extended by hits; no startup scan or VACUUM.
        with connection:
            connection.execute('DELETE FROM plans WHERE updated <= ?', (time()-TTL_SECONDS,))
    except sqlite3.Error:
        connection.close()
        raise
    return connection


def load(key):
    connection = connect()
    try:
        row = connection.execute('SELECT payload, digest FROM plans WHERE key=? AND updated > ?',
                                 (key, time()-TTL_SECONDS)).fetchone()
        if not row or sha256(row[0].encode()).hexdigest() != row[1]:
            return None
        data = json.loads(row[0])
        planned = []
        for path, placement in data['placements']:
            placement['cut_knife_xs_px'] = tuple(placement.get('cut_knife_xs_px', ()))
            planned.append((Path(path), Placement(**placement)))
        labels = {int(k): v for k, v in data['labels'].items()}
        result = planned, labels, data['width'], data['height'], data['baseline']
        return result, data['analysis'], data['knife_mm']
    finally:
        connection.close()


def save(key, result, analysis, knife_mm):
    planned, labels, width, height, baseline = result
    data = {'placements': [(str(path), asdict(p)) for path, p in planned], 'labels': labels,
            'width': width, 'height': height, 'baseline': baseline, 'analysis': analysis, 'knife_mm': knife_mm}
    payload = json.dumps(data, ensure_ascii=False)
    connection = connect()
    try:
        with connection:
            connection.execute('INSERT OR REPLACE INTO plans VALUES (?, ?, ?, ?)',
                               (key, payload, sha256(payload.encode()).hexdigest(), time()))
    finally:
        connection.close()


def cached_analysis(analysis):
    timing = analysis.get('measurement_timings')
    if timing:
        timing['cached_original_steps'] = timing['steps']
        timing['steps'] = [dict(row, seconds=0.0, calls=0) for row in timing['steps']]
        timing['cache_hit'] = True
    analysis['cache'] = {'hit': True, 'scope': '复用已完成排版与测量；生成时仍独立检查源图和输出像素'}
    comparison = analysis.get('film_comparison')
    if comparison:
        comparison['cached_original_seconds'] = comparison['seconds']
        comparison['seconds'] = comparison['measurement_seconds'] = 0
        for row in comparison['rows']:
            row['seconds'] = 0
    rotation = analysis.get('rotation_comparison')
    if rotation:
        rotation['normal_seconds'] = rotation['rotation_seconds'] = 0
    return analysis
