"""Lossless source copies with a minimum transparent gap below the label card."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import replace
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
from time import time
from uuid import uuid4

from automatic_print.layout_engine.labeling.base.header_region import search_header
from automatic_print.layout_engine.labeling.gap.preparation import (
    gap_geometry,
    gap_geometry_file,
    insert_gap,
    save_gap_copy,
)
from automatic_print.layout_engine.labeling.gap.cache_files import (
    replace_with_busy_retry,
    unlink_temporary,
)
from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.reporting.metrics import gap_report, gap_summary

TTL = 86400


def cache_root():
    from automatic_print.layout_engine.planning.cache.plan_cache import cache_directory
    return cache_directory() / '膜标签间距副本'


def prepare_one(path, settings):
    path = Path(path)
    from automatic_print.layout_engine.labeling.gap.virtual import enabled, gap_map
    virtual = enabled(settings)
    existing_virtual = gap_map(settings).get(str(path.resolve())) if virtual else None
    if existing_virtual:
        split, added, mtime_ns, size = existing_virtual
        stat = path.stat()
        if (stat.st_mtime_ns, stat.st_size) == (mtime_ns, size):
            return path, {
                'source': str(path), 'filename': path.name,
                'minimum_mm': settings.membrane_gap_mm,
                'added_px': added, 'split_px': split,
                'added_mm': added * 25.4 / print_dimensions(path, settings.dpi).y_dpi,
                'final_gap_mm': settings.membrane_gap_mm,
                'source_identity': [str(path.resolve()), mtime_ns, size],
                'prepared': str(path), 'virtual_gap': True,
                'preparation_engine': '合成时虚拟补距', 'warning': '',
            }
    root = cache_root()
    if root in path.parents:
        try:
            record = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
            verify_records([record])
            return path, record
        except (OSError, ValueError, KeyError):
            original = Path(str(locals().get('record', {}).get('source', '')))
            if original.is_file() and root not in original.parents:
                return prepare_one(original, settings)
            return path, {
                'source': str(path), 'filename': path.name,
                'minimum_mm': settings.membrane_gap_mm, 'added_px': 0,
                'warning': ('膜标签间距缓存记录损坏或缺失；已保留现有缓存图片继续排版，'
                            '可在排版缓存中清理后重新生成'),
            }
    stat = path.stat()
    fingerprint = [str(path.resolve()), stat.st_mtime_ns, stat.st_size, settings.membrane_gap_mm, 4]
    target = root / sha256(json.dumps(fingerprint).encode()).hexdigest() / path.name
    info = target.with_suffix('.json')
    if virtual:
        from automatic_print.layout_engine.labeling.gap.virtual_cache import load
        cached = load(info, path, fingerprint[:3], TTL)
        if cached is not None:
            return path, cached
    if target.is_file() and info.is_file() and time() - info.stat().st_mtime < TTL:
        try:
            record = json.loads(info.read_text(encoding='utf-8'))
            if record.get('source_identity') == fingerprint[:3]:
                return target, record
        except (OSError, ValueError):
            pass  # Damaged metadata is a cache miss, never a production failure.
    record = {'source': str(path), 'filename': path.name, 'minimum_mm': settings.membrane_gap_mm,
              'added_px': 0, 'warning': ''}
    dimensions = print_dimensions(path, settings.dpi)
    if not dimensions.embedded_dpi:
        record['warning'] = '缺少可靠DPI，未补足膜标签间距'
        return path, record
    region = search_header(path)
    if region is None:
        record['warning'] = '未找到可靠膜标签分界，未补足间距'
        return path, record
    try:
        split, added = gap_geometry_file(
            path, region, ceil(settings.membrane_gap_mm * dimensions.y_dpi / 25.4),
        )
    except ValueError as exc:
        record['warning'] = str(exc)
        return path, record
    if not added:
        record.update(final_gap_mm=settings.membrane_gap_mm,
                      source_identity=fingerprint[:3])
        if virtual:
            record.update(prepared=str(path), virtual_gap=True,
                          preparation_engine='合成时虚拟补距')
            from automatic_print.layout_engine.labeling.gap.virtual_cache import save
            save(info, record)
        return path, record
    record.update(added_px=added, split_px=split, added_mm=added*25.4/dimensions.y_dpi,
                  final_gap_mm=settings.membrane_gap_mm,
                  source_identity=fingerprint[:3], prepared=str(path if virtual else target))
    if virtual:
        record.update(virtual_gap=True, preparation_engine='合成时虚拟补距')
        from automatic_print.layout_engine.labeling.gap.virtual_cache import save
        save(info, record)
        return path, record
    temporary = target.with_name(target.name + '.' + uuid4().hex + '.未完成')
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        record['preparation_engine'] = save_gap_copy(
            path, temporary, split, added, dimensions,
        )
        if (path.stat().st_mtime_ns, path.stat().st_size) != (stat.st_mtime_ns, stat.st_size):
            raise ValueError(f'{path.name}：补足间距期间源文件发生变化')
        replace_with_busy_retry(temporary, target)
        metadata = info.with_name(info.name + '.' + uuid4().hex + '.未完成')
        try:
            metadata.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
            replace_with_busy_retry(metadata, info)
        finally:
            unlink_temporary(metadata)
    except OSError as error:
        record.update(
            added_px=0,
            warning=(f'膜标签间距缓存文件被占用或无法写入（{error}）；'
                     f'原值：补足 {settings.membrane_gap_mm:g} 毫米；采用值：保留原图间距；'
                     '影响：仅本张未补足，已继续排版；修改位置：排版设置→膜标签与图案间距'),
        )
        record.pop('prepared', None)
        return path, record
    finally:
        unlink_temporary(temporary)
    return target, record


def prepare_paths(paths, settings, progress=None):
    if settings.membrane_gap_mm <= 0:
        return list(paths), settings, []
    if settings.membrane_gap_mm > 200:
        raise ValueError('膜标签与图案最小间距必须在0至200毫米之间')
    paths = list(paths)
    if progress:
        progress('补足膜标签间距', 0, len(paths), '正在检查膜标签与图案间的空白')
    results = [None] * len(paths)
    workers = min(max(1, settings.worker_threads), 4, len(paths) or 1)
    def process(path):
        try:
            return prepare_one(path, settings)
        except Exception as error:
            path = Path(path)
            return path, {
                'source': str(path), 'filename': path.name,
                'minimum_mm': settings.membrane_gap_mm, 'added_px': 0,
                'warning': (f'补足膜标签间距时发生可恢复错误（{error}）；'
                            f'原值：补足 {settings.membrane_gap_mm:g} 毫米；'
                            '采用值：保留原图间距；影响：仅本张未补足，已继续排版；'
                            '修改位置：排版设置→膜标签与图案间距'),
            }
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='header-gap') as pool:
        iterator = iter(enumerate(paths))
        pending = {}
        def submit_next():
            entry = next(iterator, None)
            if entry is not None:
                index, path = entry
                pending[pool.submit(process, path)] = index
        for _ in range(workers):
            submit_next()
        completed = 0
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index = pending.pop(future)
                result = results[index] = future.result()
                completed += 1
                if progress:
                    progress('补足膜标签间距', completed, len(paths), result[1]['filename'] +
                             (' · ' + result[1]['warning'] if result[1]['warning'] else ''))
                submit_next()
    mapping = {str(old.resolve()): str(new.resolve()) for old, (new, _) in zip(paths, results)}
    from automatic_print.automation.api.s2b.metadata.store import register_path_aliases
    register_path_aliases(mapping)
    remap = lambda values: tuple((mapping.get(name, name), value) for name, value in values)
    virtuals = {row[0]: row[1:] for row in settings.header_gap_overrides}
    overrides = dict(settings.dimension_overrides)
    for original, (_prepared, record) in zip(paths, results):
        if not record.get('virtual_gap') or not record.get('added_px'):
            continue
        key = str(original.resolve())
        if key in virtuals:
            continue
        stat = original.stat()
        virtuals[key] = (record['split_px'], record['added_px'], stat.st_mtime_ns, stat.st_size)
        dimensions = print_dimensions(original, settings.dpi)
        width_mm, height_mm = overrides.get(key, (dimensions.width_mm, dimensions.height_mm))
        overrides[key] = (width_mm, height_mm + record['added_mm'])
    settings = replace(
        settings,
        manual_rotations=remap(settings.manual_rotations),
        sequence_numbers=remap(settings.sequence_numbers),
        dimension_overrides=tuple(overrides.items()),
        header_gap_overrides=tuple((key, *value) for key, value in virtuals.items()),
    )
    return [path for path, _ in results], settings, [record for _, record in results]


def verify_records(records):
    for record in records:
        expected = record.get('source_identity')
        if expected:
            original = Path(expected[0])
            stat = original.stat()
            if [str(original.resolve()), stat.st_mtime_ns, stat.st_size] != expected:
                raise ValueError(f'{original.name}：补足间距后源文件发生变化，请重新生成')


def annotate_analysis(data, records, settings=None, progress=None):
    data['header_gap'] = records
    if settings and settings.developer_gap_loss and 'height_m' in data:
        from automatic_print.layout_engine.planning.zones.gap_loss import compare_gap_loss
        if progress:
            progress('间距额外用膜比较', 0, 1, '原间距参考，仅几何计算，不生成图片')
        data['gap_loss'] = compare_gap_loss(records, settings, data['height_m'], progress)
        if progress:
            progress('间距额外用膜比较', 1, 1, '原间距参考计算完成')
    rows = data.setdefault('image_anomalies', [])
    if settings and settings.output_dpi_notice:
        data['output_dpi_notice'] = settings.output_dpi_notice
        if not any(row.get('kind') == settings.output_dpi_notice for row in rows):
            rows.append({'source': '整批输出DPI', 'path': '',
                         'kind': settings.output_dpi_notice, 'action': '已自动继续，可手动修改输出DPI'})
    existing = {(row['source'], row['kind']) for row in rows}
    for record in records:
        warning = record['warning']
        if warning and (record['filename'], warning) not in existing:
            rows.append({'source': record['filename'], 'path': record['source'],
                         'kind': warning, 'action': '保留原图间距；请人工核对'})
    return data
