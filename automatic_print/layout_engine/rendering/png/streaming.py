"""Final-raster corridor checks and constant-size PNG metadata validation."""
import struct
import zlib
from time import perf_counter


def validate_final_canvas(canvas, check, boxes, rectangles, progress=None):
    if check is None:
        return
    from automatic_print.layout_engine.cutting.geometry.printed_guides import vips_corridors_are_clear
    from automatic_print.layout_engine.cutting.validation.cut_validation import corridor_checks
    zones = corridor_checks(check)
    if progress:
        progress('核对最终合成通道', 0, len(zones), '一次检查全部刀位与实际标记像素')
    if not vips_corridors_are_clear(canvas, zones, boxes, rectangles):
        raise ValueError('最终合成画布进入切割安全通道，禁止输出。')
    from automatic_print.layout_engine.cutting.validation.cut_validation import mark_pixel_verified
    mark_pixel_verified(check)
    if progress:
        progress('核对最终合成通道', len(zones), len(zones), '全部刀位通道检查通过')


def validate_header(path, width, height):
    # Native lossless writer consumes the checked raster. Do not decompress it again.
    with path.open('rb') as stream:
        header = stream.read(33)
        stream.seek(-12, 2)
        ending = stream.read(12)
    expected = (width, height, 8, 6, 0, 0, 0)
    if (len(header) != 33 or header[:8] != b'\x89PNG\r\n\x1a\n'
            or header[12:16] != b'IHDR'
            or struct.unpack('>IIBBBBB', header[16:29]) != expected
            or zlib.crc32(header[12:29]) & 0xffffffff != struct.unpack('>I', header[29:33])[0]
            or ending != b'\x00\x00\x00\x00IEND\xaeB`\x82'):
        path.rename(path.with_suffix('.禁止打印'))
        raise ValueError('输出PNG尺寸或像素格式与已检查画布不一致，禁止打印。')


def validate_chunks(path, width, height):
    """Verify every stored chunk without decoding pixels checked while writing."""
    saw_header = saw_data = saw_end = False
    with path.open('rb') as stream:
        if stream.read(8) != b'\x89PNG\r\n\x1a\n':
            raise ValueError('输出文件不是有效PNG')
        while not saw_end:
            raw_length = stream.read(4)
            if len(raw_length) != 4:
                raise ValueError('输出PNG提前结束')
            length = struct.unpack('>I', raw_length)[0]
            kind = stream.read(4)
            if len(kind) != 4:
                raise ValueError('输出PNG数据块不完整')
            crc, remaining = zlib.crc32(kind), length
            header = bytearray() if kind == b'IHDR' else None
            while remaining:
                block = stream.read(min(1024 * 1024, remaining))
                if not block:
                    raise ValueError('输出PNG数据块提前结束')
                crc = zlib.crc32(block, crc)
                if header is not None:
                    header.extend(block)
                remaining -= len(block)
            stored = stream.read(4)
            if len(stored) != 4 or crc & 0xffffffff != struct.unpack('>I', stored)[0]:
                raise ValueError('输出PNG数据块校验失败')
            if kind == b'IHDR':
                expected = (width, height, 8, 6, 0, 0, 0)
                if len(header) != 13 or struct.unpack('>IIBBBBB', header) != expected:
                    raise ValueError('输出PNG尺寸或RGBA格式不正确')
                saw_header = True
            elif kind == b'IDAT':
                saw_data = True
            elif kind == b'IEND':
                saw_end = True
        if stream.read(1) or not (saw_header and saw_data and saw_end):
            raise ValueError('输出PNG结构不完整')


def validate_saved_output(path, width, height, check, boxes, rectangles,
                          progress, phase, save_details):
    phase('输出文件安全复核')
    started = perf_counter()
    try:
        from .corridor_reader import validate
        from automatic_print.layout_engine.cutting.validation.cut_validation import corridor_checks, mark_pixel_verified
        checks = corridor_checks(check)
        if save_details.get('pixel_verified_during_encoding'):
            validate_chunks(path, width, height)
        elif checks:
            validate(path, width, height, checks, boxes, rectangles, progress)
        else:
            validate_header(path, width, height)
        mark_pixel_verified(check)
    except (OSError, ValueError, zlib.error):
        forbidden = path.with_suffix('.禁止打印')
        if path.exists():
            path.rename(forbidden)
        raise ValueError('输出PNG完整性或刀位像素检查失败，已禁止打印。')
    seconds = perf_counter() - started
    name = ('输出PNG数据块CRC、尺寸与格式复核'
            if save_details.get('pixel_verified_during_encoding') else
            '输出PNG单次解压、完整性与全长刀位核对')
    save_details.setdefault('steps', []).append({'name': name, 'seconds': seconds})
    return seconds
