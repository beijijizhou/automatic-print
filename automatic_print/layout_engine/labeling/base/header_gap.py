"""Lossless source copies with a minimum transparent gap below the label card."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from time import time
from uuid import uuid4

import numpy as np
from PIL import Image

from automatic_print.layout_engine.labeling.base.header_region import search_header
from automatic_print.layout_engine.intake.metadata.images import print_dimensions

TTL = 86400


def cache_root():
    from automatic_print.layout_engine.planning.cache.plan_cache import cache_directory
    return cache_directory() / '膜标签间距副本'


def gap_geometry(source, region, minimum_px):
    """Find the first wholly transparent row below the card, then the next ink row.

    Alpha is checked across the entire width, including semi-transparent ink.
    Only insert rows: never crop, scale or remove any original pixels.
    """
    bottom = min(source.height, max(0, round(region.bottom * source.height)))
    # Card detection follows the connected white paper. Haloo cards can end in
    # an opaque coloured footer which is not connected to that white component;
    # search a bounded width-relative distance for the real transparent seam.
    tolerance = max(96, round(source.width * .08))
    end = min(source.height, bottom + tolerance + minimum_px + 1)
    with source.crop((0, bottom, source.width, end)) as strip:
        with strip.getchannel('A') as alpha:
            occupied = np.asarray(alpha).max(axis=1) > 0
    empty = np.flatnonzero(~occupied[:tolerance+1])
    if not len(empty):
        raise ValueError('膜标签下方没有可确认的透明分界，保留原图，请人工核对')
    split = bottom + int(empty[0])
    following = np.flatnonzero(occupied[int(empty[0]):])
    existing = int(following[0]) if len(following) else end - split
    return split, max(0, minimum_px - existing)


def insert_gap(source, split, added):
    canvas = Image.new('RGBA', (source.width, source.height + added))
    with source.crop((0, 0, source.width, split)) as top:
        canvas.paste(top, (0, 0))
    with source.crop((0, split, source.width, source.height)) as body:
        canvas.paste(body, (0, split + added))
    return canvas


def prepare_one(path, settings):
    path = Path(path)
    root = cache_root()
    if root in path.parents:
        record = json.loads(path.with_suffix('.json').read_text())
        verify_records([record])
        return path, record
    stat = path.stat()
    fingerprint = [str(path.resolve()), stat.st_mtime_ns, stat.st_size, settings.membrane_gap_mm, 3]
    target = root / sha256(json.dumps(fingerprint).encode()).hexdigest() / path.name
    info = target.with_suffix('.json')
    if target.is_file() and info.is_file() and time() - info.stat().st_mtime < TTL:
        try:
            record = json.loads(info.read_text())
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
    with Image.open(path) as opened, opened.convert('RGBA') as source:
        try:
            split, added = gap_geometry(source, region, round(settings.membrane_gap_mm * dimensions.y_dpi / 25.4))
        except ValueError as exc:
            record['warning'] = str(exc)
            return path, record
        if not added:
            return path, record
        record.update(added_px=added, split_px=split, added_mm=added*25.4/dimensions.y_dpi,
                      source_identity=fingerprint[:3], prepared=str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.' + uuid4().hex + '.未完成')
        try:
            with insert_gap(source, split, added) as canvas:
                canvas.save(temporary, format='PNG', dpi=(dimensions.x_dpi, dimensions.y_dpi),
                            icc_profile=opened.info.get('icc_profile'), compress_level=1)
            if (path.stat().st_mtime_ns, path.stat().st_size) != (stat.st_mtime_ns, stat.st_size):
                raise ValueError(f'{path.name}：补足间距期间源文件发生变化')
            temporary.replace(target)
            metadata = info.with_name(info.name + '.' + uuid4().hex + '.未完成')
            try:
                metadata.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
                metadata.replace(info)
            finally:
                metadata.unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)
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
        return prepare_one(path, settings)
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
    remap = lambda values: tuple((mapping.get(name, name), value) for name, value in values)
    settings = replace(settings, manual_rotations=remap(settings.manual_rotations),
                       sequence_numbers=remap(settings.sequence_numbers))
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


def gap_report(records):
    if not records:
        return ''
    changed = [record for record in records if record['added_px']]
    rolled = [r for r in records if r.get('rollback_added_mm')]
    return (gap_summary(records) + '\n' +
            '\n'.join(f"{r['filename']}：新增透明空白{r['added_mm']:.2f}毫米" for r in changed)+
            '\n'+'\n'.join(f"{r['filename']}：已回退新增{r['rollback_added_mm']:.2f}毫米；用户设置未修改" for r in rolled))


def gap_summary(records):
    if not records:
        return ''
    changed = [record for record in records if record.get('added_px')]
    warnings = [record for record in records if record.get('warning')]
    rolled = [record for record in records if record.get('rollback_added_mm')]
    already = len(records) - len(changed) - len(warnings) - len(rolled)
    added = ''
    if changed:
        low = min(record['added_mm'] for record in changed)
        high = max(record['added_mm'] for record in changed)
        added = (f' · 每张新增 {low:.2f} 毫米' if abs(high-low) < .005 else
                 f' · 每张新增 {low:.2f}–{high:.2f} 毫米')
    rollback = f' · 已回退 {len(rolled)} 张' if rolled else ''
    return (
        f"膜标签间距：目标 {records[0]['minimum_mm']:g} 毫米 · 共 {len(records)} 张"
        f" · 实际扩充 {len(changed)} 张 · 原本已满足 {max(0, already)} 张"
        f" · 未能扩充 {len(warnings)} 张{rollback}{added}（不缩放原图）"
    )
