"""Final-raster corridor checks and constant-size PNG metadata validation."""
import struct
import zlib


def validate_final_canvas(canvas, check, boxes, rectangles, progress=None):
    if check is None:
        return
    from ..printed_guides import vips_corridor_is_clear
    zones = check.get('zones', [check])
    for index, zone in enumerate(zones, 1):
        if progress:
            progress('核对最终合成通道', index-1, len(zones),
                     zone.get('name', '整批')+'：检查全部高度与实际标记像素')
        if not vips_corridor_is_clear(canvas, zone, boxes, rectangles):
            raise ValueError('最终合成画布进入切割安全通道，禁止输出。')
        zone['pixel_verified'] = True
    check['pixel_verified'] = True


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
