"""Persistent JSON-only geometry cache; source/output safety remains independent."""
from dataclasses import asdict, replace
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from time import time

from automatic_print.layout_engine.measurement.measurement_session import identity
from automatic_print.layout_engine.domain.models import Placement

SCHEMA = 1
LAYOUT_ALGORITHM_REVISION = 13
DEVELOPER_LAYOUT_ALGORITHM_REVISION = 22
SHARED_KNIFE_LAYOUT_ALGORITHM_REVISION = 8
ORDER_SIDE_LAYOUT_ALGORITHM_REVISION = 4
TTL_SECONDS = 24 * 60 * 60
CACHE_LOCK_TIMEOUT_SECONDS = .25


def cache_directory():
    from automatic_print.runtime.crash_logging import log_folder
    return log_folder()


def cache_key(paths, settings, created_at, progress=None):
    template = settings.label_text_template
    date = created_at.strftime(settings.label_date_format) if ('{日期}' in template or '{date' in template) else ''
    identity_workers = max(1, min(8, int(settings.worker_threads), len(paths)))
    settings = replace(settings,
                       label_batch_name=(settings.label_batch_name
                                         if settings.label_source_order_enabled else ''),
                       worker_threads=1, output_parts=1, save_parallelism=1,
                       save_memory_mb=512, save_memory_unlimited=False, png_engine='pillow',
                       output_format='png', png_compression_level=1,
                       png_fast_encoding=False, png_streaming=False,
                       film_geometry_workers=1)
    if identity_workers == 1:
        files = [identity(path) for path in paths]
    else:
        with ThreadPoolExecutor(max_workers=identity_workers, thread_name_prefix='cache-identity') as pool:
            futures = [pool.submit(copy_context().run, identity, path) for path in paths]
            files = [future.result() for future in futures]
    if progress:
        progress('读取排版缓存', len(paths), len(paths),
                 f'已一次读取{len(paths)}个文件状态（{identity_workers}路并行）')
    settings_data = asdict(settings)
    settings_data.pop('header_gap_overrides', None)
    developer_knife_gap = settings.cutter_knife_change_gap_mm > 0
    developer_compact = settings.developer_compact_cutter_layout
    # This feature is strictly isolated from production mode.  In particular,
    # the added field must not perturb the legacy production cache key merely
    # because a newer binary contains it.
    if not developer_knife_gap:
        settings_data.pop('cutter_knife_change_gap_mm', None)
    if not developer_compact:
        settings_data.pop('developer_compact_cutter_layout', None)
    if not settings.order_side_shared_knife:
        settings_data.pop('order_side_shared_knife', None)
    algorithm_revision = (ORDER_SIDE_LAYOUT_ALGORITHM_REVISION
                          if settings.order_side_shared_knife else
                          SHARED_KNIFE_LAYOUT_ALGORITHM_REVISION
                          if settings.strict_fixed_knife else
                          DEVELOPER_LAYOUT_ALGORITHM_REVISION
                          if developer_knife_gap or developer_compact
                          else LAYOUT_ALGORITHM_REVISION)
    data = {'schema': SCHEMA, 'algorithm': algorithm_revision, 'files': files,
            'settings': settings_data, 'date': date, 'font_revision': 1}
    if settings.platform_reuse_qr:
        # Old plans placed text into the source membrane card and cached both
        # its geometry and label strings.  Rebuild only affected plans.
        data['production_label_revision'] = 2
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def connect():
    directory = cache_directory()
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        directory/'排版缓存.sqlite3', timeout=CACHE_LOCK_TIMEOUT_SECONDS,
    )
    try:
        connection.execute(
            f'PRAGMA busy_timeout={round(CACHE_LOCK_TIMEOUT_SECONDS * 1000)}'
        )
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
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
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
