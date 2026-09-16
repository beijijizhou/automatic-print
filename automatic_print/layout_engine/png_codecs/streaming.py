"""Final-raster corridor checks and constant-size PNG metadata validation."""
import struct
import zlib
from time import perf_counter


def validate_final_canvas(canvas, check, boxes, rectangles, progress=None):
    if check is None:
        return
    from ..printed_guides import vips_corridors_are_clear
    from ..cut_validation import corridor_checks
    zones = corridor_checks(check)
    if progress:
        progress('核对最终合成通道', 0, len(zones), '一次检查全部刀位与实际标记像素')
    if not vips_corridors_are_clear(canvas, zones, boxes, rectangles):
        raise ValueError('最终合成画布进入切割安全通道，禁止输出。')
    from ..cut_validation import mark_pixel_verified
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


def validate_saved_output(path, width, height, check, boxes, rectangles,
                          progress, phase, save_details):
    phase('输出尺寸核对')
    validate_header(path, width, height)
    phase('输出PNG刀位像素复核')
    started = perf_counter()
    from ..cut_validation import validate_vips_output
    validate_vips_output(path, check, progress, boxes, rectangles)
    seconds = perf_counter() - started
    save_details.setdefault('steps', []).append({
        'name': '输出PNG全长刀位像素复核', 'seconds': seconds,
    })
    return seconds
