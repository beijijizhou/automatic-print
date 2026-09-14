"""Standard RGBA PNG with vectorized UP filtering and native libdeflate."""
import struct
import zlib
from time import perf_counter

import numpy as np

try:
    from imagecodecs import deflate_encode
except (ImportError, OSError):
    deflate_encode = None


class FastEncodingError(RuntimeError):
    """Codec failure only; never swallow cancellation from progress callbacks."""


def chunk(kind, data):
    crc = zlib.crc32(data, zlib.crc32(kind)) & 0xffffffff
    return struct.pack('>I', len(data)), kind, data, struct.pack('>I', crc)


def encode_pixels(pixels, level):
    height, width, channels = pixels.shape
    if pixels.dtype != np.uint8 or channels != 4:
        raise ValueError('快速PNG保存只接受8位RGBA像素。')
    if deflate_encode is None:
        raise RuntimeError('原生快速压缩库不可用')
    rows = pixels.reshape(height, width*4)
    filtered = np.empty((height, width*4+1), dtype=np.uint8)
    filtered[:, 0] = 2  # Standard PNG UP filter; arithmetic wraps modulo 256.
    filtered[0, 0] = 0
    filtered[0, 1:] = rows[0]
    np.subtract(rows[1:], rows[:-1], out=filtered[1:, 1:])
    # libdeflate's levels differ from zlib's. Level 1 prioritizes speed.
    encoded = deflate_encode(filtered, level=level, raw=False)
    return encoded


def save(canvas, target, settings, use_vips, progress=None):
    steps = []
    def measured(name, function):
        start = perf_counter()
        value = function()
        steps.append({'name': name, 'seconds': perf_counter()-start})
        return value
    def report(name):
        if progress:
            progress('保存图片', 0, 0, name+' · '+target.name)
    report('准备快速保存像素')
    if use_vips:
        width, height = canvas.width, canvas.height
        pixels = measured('延迟合成与像素提取', lambda: np.frombuffer(
            canvas.write_to_memory(), dtype=np.uint8).reshape(height, width, 4))
    else:
        width, height = canvas.size
        pixels = measured('保存像素提取', lambda: np.asarray(canvas))
    report('快速滤波与压缩')
    def compress():
        try:
            return encode_pixels(pixels, settings.png_compression_level)
        except (RuntimeError, ValueError) as error:
            raise FastEncodingError(str(error)) from error
    encoded = measured('快速滤波与PNG压缩', compress)
    del pixels
    ppm = round(settings.dpi/0.0254)
    header = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    density = struct.pack('>IIB', ppm, ppm, 1)
    report('写入PNG文件')
    def write():
        with target.open('wb') as stream:
            stream.write(b'\x89PNG\r\n\x1a\n')
            for kind, data in ((b'IHDR', header), (b'pHYs', density)):
                for piece in chunk(kind, data):
                    stream.write(piece)
            view = memoryview(encoded)
            for offset in range(0, len(view), 4*1024*1024):
                for piece in chunk(b'IDAT', view[offset:offset+4*1024*1024]):
                    stream.write(piece)
                if progress:
                    progress('保存图片', stream.tell(), 0, target.name)
            for piece in chunk(b'IEND', b''):
                stream.write(piece)
    measured('PNG文件写入', write)
    return {'encoder': '原生快速PNG（固定UP滤波、libdeflate）', 'steps': steps}


def timing_text(data):
    if not data:
        return ''
    text = ['保存编码器：'+data['encoder']]
    text.extend(f"{row['name']}：{row['seconds']:.3f} 秒" for row in data.get('steps', []))
    if data.get('fallback_reason'):
        text.append('兼容回退：'+data['fallback_reason'])
    return '\n'.join(text)


def result_timing_text(result):
    parts = result.get('parts')
    if not parts:
        return timing_text(result.get('png_save_details'))
    lines = ['各段保存子步骤（可并行重叠，不与总耗时相加）']
    for part in parts:
        lines.append(part['filename']+'\n'+timing_text(part.get('png_save_details')))
    return '\n'.join(lines)
