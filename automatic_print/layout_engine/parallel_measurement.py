"""Bounded, ordered per-image measurements with thread-local decoded sources."""
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from contextvars import copy_context
from dataclasses import replace
from .measurement_session import measurement_session
from .images import print_dimensions


def read_parallel(read_one, paths, settings, progress):
    workers = measurement_workers(settings.worker_threads,len(paths))
    if workers == 1 or len(paths) < 4:
        return read_one(paths, settings, progress)
    numbers = dict(settings.sequence_numbers)
    def calculate(index, path):
        config = replace(settings, sequence_numbers=((str(path.resolve()),
                          numbers.get(str(path.resolve()), index)),))
        return read_one([path], config, None)
    items, labels, pending = [], {}, {}
    results=[None]*len(paths)
    source = iter(enumerate(paths))
    if progress:
        progress('读取图片尺寸', 0, len(paths), f'尺寸、膜标签与刀码最多{workers}路并行测量')
    with measurement_session(), ThreadPoolExecutor(max_workers=workers, thread_name_prefix='image-measure') as pool:
        def submit():
            entry = next(source, None)
            if entry:
                index, path = entry
                future=pool.submit(copy_context().run,calculate,index+1,path)
                pending[future]=(index,path)
        try:
            for _ in range(workers):
                submit()
            completed=0
            while pending:
                done,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    index,path=pending.pop(future)
                    results[index]=future.result()
                    completed+=1
                    if progress:
                        size = print_dimensions(path, settings.dpi)
                        dpi = '图片内嵌 DPI' if size.embedded_dpi else '缺少 DPI，按输出 DPI 估算'
                        progress('测量标签与刀码', completed, len(paths),
                                 f'{path.name} · {size.width_mm:.1f} × {size.height_mm:.1f} 毫米 · {dpi}')
                    submit()
        finally:
            for future in pending:
                future.cancel()
    for choices,texts in results:
        items.extend(choices)
        labels.update(texts)
    return items, labels


def measurement_workers(configured,total):
    """Honor the user setting while bounding concurrent source decodes."""
    return max(1,min(8,int(configured),int(total)))
