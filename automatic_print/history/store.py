"""Durable numeric comparison history, independent of image output folders."""
import csv
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .. import __version__, __version_display__
from ..crash_logging import log_folder


def history_path():
    return log_folder() / '用膜历史.sqlite3'


@contextmanager
def database(path=None):
    path = Path(path) if path else history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    try:
        connection.execute('CREATE TABLE IF NOT EXISTS runs '
                           '(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
        with connection:
            yield connection
    finally:
        connection.close()


def save_run(job_id, source, output, settings, result, path=None):
    analysis = result.get('analysis', {})
    comparison = analysis.get('film_comparison')
    if not comparison:
        return None
    from dataclasses import asdict
    record = {'schema_version': 1, 'id': job_id,
              'created_at': datetime.now().astimezone().isoformat(),
              'version': __version__, 'version_display': __version_display__,
              'source_folder': str(Path(source).resolve()), 'batch_name': Path(source).name,
              'output_folder': str(output) if not result.get('preview_only') else '',
              'status': '仅预览' if result.get('preview_only') else '已生成',
              'settings': asdict(settings),
              'image_count': analysis.get('image_count'),
              'order_count': analysis.get('order_count'),
              'comparison': comparison, 'timings': result.get('operation_timings', {}),
              'selected_length_m': result.get('height_mm', 0)/1000 or analysis.get('height_m')}
    with database(path) as connection:
        connection.execute('INSERT OR REPLACE INTO runs VALUES (?, ?, ?)',
                           (job_id, record['created_at'], json.dumps(record, ensure_ascii=False)))
    return record


def load_runs(path=None):
    with database(path) as connection:
        return [json.loads(row[0]) for row in connection.execute(
            'SELECT payload FROM runs ORDER BY created_at DESC, id DESC')]


def export_csv(destination, records):
    columns = ['记录编号', '时间', '批次', '来源', '状态', '版本', '图片数', '订单数',
               '实际膜宽毫米', '左预留毫米', '右预留毫米', '方案膜宽毫米', '可用宽毫米',
               '允许旋转', '现有规格', '长度米', '耗膜平方米', '可用面积平方米',
               '图片面积平方米', '图片占位百分比', '可用区占位百分比', '旋转图片数', '计算秒', '异常']
    with Path(destination).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for record in records:
            settings = record['settings']
            for row in record['comparison']['rows']:
                writer.writerow([record['id'], record['created_at'], record['batch_name'],
                    record['source_folder'], record['status'], record['version'],
                    record['image_count'], record['order_count'], settings['media_width_mm']+
                    settings['riin_left_mm']+settings['riin_right_mm'],
                    settings['riin_left_mm'], settings['riin_right_mm'], row['film_mm'],
                    row['usable_mm'], row['rotation_allowed'], row.get('available', True),
                    *[row.get(key, '') for key in ('length_m', 'film_area_m2', 'usable_area_m2',
                      'image_area_m2', 'image_occupancy_percent', 'usable_occupancy_percent',
                      'rotated_images', 'seconds', 'error')]])
