"""Lossless source copies with a minimum transparent gap below the label card."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextvars import copy_context
from dataclasses import replace
from pathlib import Path

from automatic_print.layout_engine.labeling.base.header_region import search_header
from automatic_print.layout_engine.labeling.gap.preparation import (
    gap_geometry,
    insert_gap,
)
from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.reporting.metrics import gap_report, gap_summary
from automatic_print.layout_engine.labeling.gap.cached_copy import (
    annotate_analysis, cache_root, prepare_one as _prepare_one, verify_records,
)


def prepare_one(path, settings):
    return _prepare_one(path, settings, cache_root, search_header)


def prepare_paths(paths, settings, progress=None, premeasure=None):
    if settings.membrane_gap_mm <= 0:
        return list(paths), settings, []
    if settings.membrane_gap_mm > 200:
        raise ValueError('膜标签与图案最小间距必须在0至200毫米之间')
    paths = list(paths)
    if progress:
        progress('补足膜标签间距', 0, len(paths), '正在检查膜标签与图案间的空白')
    results = [None] * len(paths)
    workers = min(max(1, settings.worker_threads), 4, len(paths) or 1)
    def process(index, path):
        from automatic_print.layout_engine.measurement.measurement_session import measuring_source
        with measuring_source(path):
            try:
                result = prepare_one(path, settings)
                if premeasure is not None:
                    premeasure(index, path, _record_settings(path, settings, result[1]))
                return result
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
                context = copy_context()
                pending[pool.submit(context.run, process, index, path)] = index
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
def _record_settings(path, settings, record):
    """Expose one virtual gap to same-pass item measurement."""
    if not record.get('virtual_gap') or not record.get('added_px'):
        return settings
    key = str(path.resolve())
    dimensions = print_dimensions(path, settings.dpi)
    overrides = dict(settings.dimension_overrides)
    width_mm, height_mm = overrides.get(
        key, (dimensions.width_mm, dimensions.height_mm)
    )
    overrides[key] = (width_mm, height_mm + record['added_mm'])
    return replace(settings, dimension_overrides=tuple(overrides.items()))
