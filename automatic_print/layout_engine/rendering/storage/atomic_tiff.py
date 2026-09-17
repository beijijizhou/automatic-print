"""Atomically publish a striped BigTIFF with bounded, parallel compression."""
from math import ceil
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from imagecodecs import deflate_encode

from automatic_print.layout_engine.rendering.storage.save_progress import monitor_save


STRIP_HEIGHT = 1024


def _compress_strip(strip, level):
    # TIFF horizontal predictor; uint8 arithmetic intentionally wraps.
    strip[:, 1:] = strip[:, 1:] - strip[:, :-1]
    return deflate_encode(strip, level=level)


class StripSource:
    def __init__(self, canvas, level, workers, progress=None):
        self.canvas = canvas
        self.level = level
        self.workers = max(1, workers)
        self.progress = progress
        self.total = ceil(canvas.height / STRIP_HEIGHT)
        self.started = perf_counter()
        self.first_ready = None
        self.exhausted = None

    def __iter__(self):
        current = 0
        pending = []
        with ThreadPoolExecutor(
            max_workers=self.workers, thread_name_prefix='tiff-deflate'
        ) as pool:
            for y in range(0, self.canvas.height, STRIP_HEIGHT):
                height = min(STRIP_HEIGHT, self.canvas.height - y)
                region = self.canvas.crop(0, y, self.canvas.width, height)
                pixels = np.frombuffer(
                    region.write_to_memory(), dtype=np.uint8
                ).reshape(height, self.canvas.width, region.bands)
                if region.bands == 4:
                    strip = pixels.copy()
                else:
                    strip = np.empty((height, self.canvas.width, 4), dtype=np.uint8)
                    strip[:, :, :3] = pixels[:, :, :3]
                    strip[:, :, 3] = 255
                if self.first_ready is None:
                    self.first_ready = perf_counter()
                pending.append(pool.submit(_compress_strip, strip, self.level))
                if len(pending) < self.workers:
                    continue
                current += 1
                yield self._completed(pending.pop(0), current)
            self.exhausted = perf_counter()
            while pending:
                current += 1
                yield self._completed(pending.pop(0), current)

    def _completed(self, future, current):
        encoded = future.result()
        if self.progress:
            self.progress('保存图片', current, self.total,
                          f'并行 Strip TIFF · {current}/{self.total}')
        return encoded


def save_tiff(canvas, target, settings, progress=None):
    """Write one RGBA BigTIFF; tifffile compresses independent tiles in parallel."""
    import tifffile

    pending = target.with_name(target.name + '.未完成')
    workers = max(1, settings.worker_threads)
    source = StripSource(
        canvas, settings.png_compression_level, workers, progress)
    started = perf_counter()
    with monitor_save(pending, progress) as observation:
        tifffile.imwrite(
            pending,
            iter(source),
            shape=(canvas.height, canvas.width, 4),
            dtype=np.uint8,
            photometric='rgb',
            extrasamples=('unassalpha',),
            rowsperstrip=STRIP_HEIGHT,
            compression='deflate',
            predictor=True,
            bigtiff=True,
            resolution=(settings.dpi, settings.dpi),
            resolutionunit='INCH',
            metadata=None,
        )
    encoded = perf_counter()
    first = source.first_ready or encoded
    exhausted = source.exhausted or encoded
    published = perf_counter()
    pending.rename(target)
    finished = perf_counter()
    return {
        'encoder': f'并行分块 BigTIFF（{workers} 线程）',
        'steps': [
            {'name': '首个 TIFF Strip 像素准备', 'seconds': first - started},
            {'name': '分块生成、并行 Deflate 压缩与写入', 'seconds': exhausted - first},
            {'name': '剩余 Strip 写入与 TIFF 索引收尾', 'seconds': encoded - exhausted},
            {'name': '未完成文件原子发布', 'seconds': finished - published},
        ],
        'production_seconds': encoded - started,
        'observed_bytes': observation.bytes_written,
        'rows_per_strip': STRIP_HEIGHT,
        'strip_count': source.total,
        'worker_threads': workers,
        'timing_note': (
            'Strip 像素生成、压缩和写入以有界流水线重叠；各阶段按生成器边界拆分，'
            '不把重叠墙钟时间重复相加。'
        ),
    }
