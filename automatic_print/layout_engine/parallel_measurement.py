"""Bounded, ordered per-image measurements with thread-local decoded sources."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import replace
from .measurement_session import measurement_session
from .images import print_dimensions


def read_parallel(read_one, paths, settings, progress):
    workers = max(1, min(4, settings.worker_threads, len(paths)))
    if workers == 1 or len(paths) < 4:
        return read_one(paths, settings, progress)
    numbers = dict(settings.sequence_numbers)
    def calculate(index, path):
        config = replace(settings, sequence_numbers=((str(path.resolve()),
                          numbers.get(str(path.resolve()), index)),))
        return read_one([path], config, None)
    items, labels, pending = [], {}, deque()
    source = iter(enumerate(paths, 1))
    if progress:
        progress('读取图片尺寸', 0, len(paths), f'尺寸、膜标签与刀码最多{workers}路并行测量')
    with measurement_session(), ThreadPoolExecutor(max_workers=workers, thread_name_prefix='image-measure') as pool:
        def submit():
            entry = next(source, None)
            if entry:
                index, path = entry
                pending.append((path, pool.submit(copy_context().run, calculate, index, path)))
        try:
            for _ in range(workers):
                submit()
            while pending:
                path, future = pending.popleft()
                choices, texts = future.result()
                items.extend(choices)
                labels.update(texts)
                if progress:
                    size = print_dimensions(path, settings.dpi)
                    dpi = '图片内嵌 DPI' if size.embedded_dpi else '缺少 DPI，按输出 DPI 估算'
                    progress('测量标签与刀码', len(items), len(paths),
                             f'{path.name} · {size.width_mm:.1f} × {size.height_mm:.1f} 毫米 · {dpi}')
                submit()
        finally:
            for _, future in pending:
                future.cancel()
    return items, labels
