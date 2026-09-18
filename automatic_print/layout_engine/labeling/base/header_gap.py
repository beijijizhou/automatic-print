"""Lossless source copies with a minimum transparent gap below the label card."""
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


from automatic_print.layout_engine.labeling.gap.batch import prepare_paths
from automatic_print.layout_engine.labeling.gap.report import annotate_analysis, verify_records
