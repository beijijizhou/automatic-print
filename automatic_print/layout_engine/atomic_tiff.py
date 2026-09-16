"""Atomically publish a tiled BigTIFF with bounded, parallel compression."""
from math import ceil
from time import perf_counter

import numpy as np

from .save_progress import monitor_save


TILE_WIDTH = 256
TILE_HEIGHT = 256


class TileSource:
    def __init__(self, canvas, progress=None):
        self.canvas = canvas
        self.progress = progress
        self.total = ceil(canvas.width / TILE_WIDTH) * ceil(canvas.height / TILE_HEIGHT)
        self.started = perf_counter()
        self.first_ready = None
        self.exhausted = None

    def __iter__(self):
        current = 0
        for y in range(0, self.canvas.height, TILE_HEIGHT):
            for x in range(0, self.canvas.width, TILE_WIDTH):
                width = min(TILE_WIDTH, self.canvas.width - x)
                height = min(TILE_HEIGHT, self.canvas.height - y)
                region = self.canvas.crop(x, y, width, height)
                pixels = np.frombuffer(region.write_to_memory(), dtype=np.uint8)
                pixels = pixels.reshape(height, width, region.bands)
                tile = np.zeros((TILE_HEIGHT, TILE_WIDTH, 4), dtype=np.uint8)
                tile[:height, :width, :min(4, region.bands)] = pixels[:, :, :4]
                if region.bands == 3:
                    tile[:height, :width, 3] = 255
                current += 1
                if self.first_ready is None:
                    self.first_ready = perf_counter()
                if self.progress:
                    self.progress('保存图片', current, self.total,
                                  f'并行分块 TIFF · {current}/{self.total}')
                yield tile
        self.exhausted = perf_counter()


def save_tiff(canvas, target, settings, progress=None):
    """Write one RGBA BigTIFF; tifffile compresses independent tiles in parallel."""
    import tifffile

    pending = target.with_name(target.name + '.未完成')
    source = TileSource(canvas, progress)
    started = perf_counter()
    with monitor_save(pending, progress) as observation:
        tifffile.imwrite(
            pending,
            iter(source),
            shape=(canvas.height, canvas.width, 4),
            dtype=np.uint8,
            photometric='rgb',
            extrasamples=('unassalpha',),
            tile=(TILE_HEIGHT, TILE_WIDTH),
            compression='deflate',
            compressionargs={'level': settings.png_compression_level},
            predictor=True,
            bigtiff=True,
            resolution=(settings.dpi, settings.dpi),
            resolutionunit='INCH',
            metadata=None,
            maxworkers=max(1, settings.worker_threads),
        )
    encoded = perf_counter()
    first = source.first_ready or encoded
    exhausted = source.exhausted or encoded
    published = perf_counter()
    pending.rename(target)
    finished = perf_counter()
    return {
        'encoder': f'并行分块 BigTIFF（{max(1, settings.worker_threads)} 线程）',
        'steps': [
            {'name': '首个 TIFF Tile 像素准备', 'seconds': first - started},
            {'name': '分块生成、并行 Deflate 压缩与写入', 'seconds': exhausted - first},
            {'name': '剩余 Tile 写入与 TIFF 索引收尾', 'seconds': encoded - exhausted},
            {'name': '未完成文件原子发布', 'seconds': finished - published},
        ],
        'production_seconds': encoded - started,
        'observed_bytes': observation.bytes_written,
        'tile': f'{TILE_WIDTH}×{TILE_HEIGHT}',
        'tile_count': source.total,
        'worker_threads': max(1, settings.worker_threads),
        'timing_note': (
            'Tile 像素生成、压缩和写入以有界流水线重叠；各阶段按生成器边界拆分，'
            '不把重叠墙钟时间重复相加。'
        ),
    }
