"""Bounded row-at-a-time RGBA PNG writer for very tall production layouts."""
import struct
from time import perf_counter
import zlib

import numpy as np

from .fast import chunk
from automatic_print.layout_engine.cutting.geometry.printed_guides import paint_guides
from automatic_print.layout_engine.rendering.storage.save_progress import monitor_save
from automatic_print.layout_engine.cutting.geometry.transition_marks import paint_transition_lines


STRIP_ROWS = 8192


def save(rows, target, width, height, settings, guide_boxes, rectangles, progress,
         cut_check=None):
    """Render each planned layout row once, then filter/compress in Y order."""
    pending = target.with_name(target.name + '.未完成')
    started = perf_counter()
    first_pixels = [None]
    rendered_rows = [0]
    strategy = (zlib.Z_RLE if settings.png_compression_level <= 1
                else zlib.Z_DEFAULT_STRATEGY)
    compressor = zlib.compressobj(
        settings.png_compression_level,
        zlib.DEFLATED,
        zlib.MAX_WBITS,
        zlib.DEF_MEM_LEVEL,
        strategy,
    )
    previous = np.zeros(width * 4, dtype=np.uint8)
    ppm = round(settings.dpi / 0.0254)
    header = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    density = struct.pack('>IIB', ppm, ppm, 1)
    from automatic_print.layout_engine.cutting.validation.cut_validation import corridor_checks
    checks = corridor_checks(cut_check)
    if checks:
        from .corridor_reader import _allowed_shapes, _shape_events
        shapes = _allowed_shapes(guide_boxes, rectangles)
        starts, ends = _shape_events(shapes)
        active = set()
    else:
        shapes, starts, ends, active = (), {}, {}, set()

    def write_chunk(stream, kind, data):
        for piece in chunk(kind, data):
            stream.write(piece)

    def emit(stream, image, top):
        nonlocal previous
        image = _decorate(image, top, guide_boxes, rectangles)
        pixels = np.frombuffer(
            image.write_to_memory(), dtype=np.uint8
        ).reshape(image.height, width * 4)
        if checks:
            from .corridor_reader import _check_row
            for local_y, alpha in enumerate(pixels[:, 3::4]):
                _check_row(top + local_y, alpha, checks, shapes,
                           starts, ends, active)
        if first_pixels[0] is None:
            first_pixels[0] = perf_counter()
        filtered = np.empty((image.height, width * 4 + 1), dtype=np.uint8)
        filtered[:, 0] = 2
        np.subtract(pixels[0], previous, out=filtered[0, 1:])
        if image.height > 1:
            np.subtract(pixels[1:], pixels[:-1], out=filtered[1:, 1:])
        previous = pixels[-1].copy()
        encoded = compressor.compress(filtered)
        if encoded:
            write_chunk(stream, b'IDAT', encoded)

    def emit_blank(stream, top, count):
        import pyvips
        while count:
            boundaries = [
                value - top
                for rectangle in rectangles
                for value in (rectangle['y'], rectangle['y'] + rectangle['height'])
                if top < value < top + count
            ]
            rows_now = min(count, STRIP_ROWS, min(boundaries, default=STRIP_ROWS))
            blank = pyvips.Image.black(width, rows_now, bands=4).copy(
                interpretation='srgb'
            )
            emit(stream, blank, top)
            top += rows_now
            count -= rows_now

    with monitor_save(pending, progress) as observation:
        with pending.open('wb') as stream:
            stream.write(b'\x89PNG\r\n\x1a\n')
            write_chunk(stream, b'IHDR', header)
            write_chunk(stream, b'pHYs', density)
            current_y = 0
            for index, (row_y, row_height, row_image) in enumerate(rows, 1):
                if row_y < current_y:
                    raise ValueError('排版行发生垂直重叠，禁止生成输出。')
                emit_blank(stream, current_y, row_y - current_y)
                emit(stream, row_image, row_y)
                current_y = row_y + row_height
                rendered_rows[0] = index
                if progress:
                    progress('保存图片', index, len(rows),
                             f'逐行合成、压缩与写入 · {index}/{len(rows)}')
            emit_blank(stream, current_y, height - current_y)
            write_chunk(stream, b'IDAT', compressor.flush())
            write_chunk(stream, b'IEND', b'')
    encoded = perf_counter()
    publish_started = perf_counter()
    pending.rename(target)
    finished = perf_counter()
    first = first_pixels[0] or encoded
    return {
        'encoder': '原生逐行流式PNG（固定UP滤波、无损RLE）',
        'steps': [
            {'name': '首行像素准备', 'seconds': first - started},
            {'name': '逐行生成、过滤、压缩与写入', 'seconds': encoded - first},
            {'name': '未完成文件原子发布', 'seconds': finished - publish_started},
        ],
        'production_seconds': encoded - started,
        'observed_bytes': observation.bytes_written,
        'rendered_rows': rendered_rows[0],
        'pixel_verified_during_encoding': bool(checks),
        'timing_note': '每个排版行只解码合成一次；单一编码流保持PNG从上到下的行顺序。',
    }


def _decorate(image, top, boxes, rectangles):
    bottom = top + image.height
    local_boxes = [
        (x, y - top, diameter) for x, y, diameter in boxes
        if y < bottom and y + diameter > top
    ]
    local_rectangles = []
    for rectangle in rectangles:
        y0 = max(top, rectangle['y'])
        y1 = min(bottom, rectangle['y'] + rectangle['height'])
        if y1 <= y0:
            continue
        local = dict(rectangle)
        local['y'] = y0 - top
        local['height'] = y1 - y0
        if 'text' in local and (y0 != rectangle['y'] or y1 != rectangle['y'] + rectangle['height']):
            raise ValueError('批次信息跨越流式分块边界，禁止生成输出。')
        local_rectangles.append(local)
    image = paint_guides(image, local_boxes, True)
    return paint_transition_lines(image, local_rectangles, True)
