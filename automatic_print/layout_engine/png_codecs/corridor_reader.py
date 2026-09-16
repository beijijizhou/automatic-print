"""Single-pass PNG integrity and knife-corridor validation."""
from collections import defaultdict
from dataclasses import dataclass
import struct
import zlib

import numpy as np


@dataclass(frozen=True)
class _Shape:
    x: int
    y: int
    width: int
    height: int
    alpha: np.ndarray | None


def validate(path, width, height, checks, boxes=(), rectangles=(), progress=None):
    """Decode fixed-UP RGBA PNG rows once and inspect every active corridor."""
    checks = list(checks)
    shapes = _allowed_shapes(boxes, rectangles)
    starts, ends = _shape_events(shapes)
    active = set()
    previous_alpha = np.zeros(width, dtype=np.uint8)
    pending = bytearray()
    pending_offset = 0
    row_bytes = width * 4
    row_stride = row_bytes + 1
    row_index = 0
    inflater = zlib.decompressobj()
    saw_header = saw_end = False

    def consume(data):
        nonlocal pending, pending_offset, previous_alpha, row_index
        pending.extend(data)
        while len(pending) - pending_offset >= row_stride:
            filter_type = pending[pending_offset]
            if filter_type not in (0, 2):
                raise ValueError(f'输出PNG使用了未核验的滤波方式 {filter_type}')
            filtered = np.frombuffer(
                pending, dtype=np.uint8, count=row_bytes,
                offset=pending_offset + 1,
            )[3::4].copy()
            if filter_type == 2:
                np.add(filtered, previous_alpha, out=filtered, casting='unsafe')
            previous_alpha = filtered
            _check_row(row_index, filtered, checks, shapes, starts, ends, active)
            row_index += 1
            pending_offset += row_stride
            if progress and (row_index % 4096 == 0 or row_index == height):
                progress('核对输出刀位通道', min(row_index, height), height,
                         '单次顺序解压并检查全部刀位')
        if pending_offset >= 4 * 1024 * 1024:
            pending = pending[pending_offset:]
            pending_offset = 0

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
            crc = zlib.crc32(kind)
            remaining = length
            header_data = bytearray() if kind == b'IHDR' else None
            while remaining:
                block = stream.read(min(1024 * 1024, remaining))
                if not block:
                    raise ValueError('输出PNG数据块提前结束')
                crc = zlib.crc32(block, crc)
                if header_data is not None:
                    header_data.extend(block)
                elif kind == b'IDAT':
                    consume(inflater.decompress(block))
                remaining -= len(block)
            stored_crc = stream.read(4)
            if len(stored_crc) != 4 or (crc & 0xffffffff) != struct.unpack('>I', stored_crc)[0]:
                raise ValueError('输出PNG数据块校验失败')
            if kind == b'IHDR':
                expected = (width, height, 8, 6, 0, 0, 0)
                if len(header_data) != 13 or struct.unpack('>IIBBBBB', header_data) != expected:
                    raise ValueError('输出PNG尺寸或RGBA格式不正确')
                saw_header = True
            elif kind == b'IEND':
                if length:
                    raise ValueError('输出PNG结尾不正确')
                saw_end = True
        consume(inflater.flush())
        if stream.read(1):
            raise ValueError('输出PNG结尾后存在异常数据')
    if not saw_header or not inflater.eof or row_index != height:
        raise ValueError('输出PNG像素数据不完整')
    if len(pending) != pending_offset:
        raise ValueError('输出PNG包含多余像素数据')


def _allowed_shapes(boxes, rectangles):
    from ..printed_guides import dot_sprite
    shapes = []
    for x, y, diameter in boxes:
        with dot_sprite(diameter) as sprite:
            alpha = np.asarray(sprite.getchannel('A'), dtype=np.uint8).copy()
        shapes.append(_Shape(x, y, diameter, diameter, alpha))
    for rectangle in rectangles:
        if 'text' in rectangle:
            from ..batch_footer import footer_sprite
            with footer_sprite(rectangle) as sprite:
                alpha = np.asarray(sprite.getchannel('A'), dtype=np.uint8).copy()
        else:
            alpha = None
        shapes.append(_Shape(
            rectangle['x'], rectangle['y'], rectangle['width'],
            rectangle['height'], alpha,
        ))
    return shapes


def _shape_events(shapes):
    starts, ends = defaultdict(list), defaultdict(list)
    for index, shape in enumerate(shapes):
        starts[shape.y].append(index)
        ends[shape.y + shape.height].append(index)
    return starts, ends


def _check_row(y, alpha, checks, shapes, starts, ends, active):
    for index in ends.get(y, ()):
        active.discard(index)
    active.update(starts.get(y, ()))
    for check in checks:
        if not check.get('start_y_px', 0) <= y < check.get('end_y_px', 2**63):
            continue
        left, right = check['safe_left_px'], check['safe_right_px']
        actual = alpha[left:right]
        if not np.any(actual):
            continue
        allowed = np.zeros(right - left, dtype=np.uint8)
        for index in sorted(active):
            shape = shapes[index]
            x0, x1 = max(left, shape.x), min(right, shape.x + shape.width)
            if x1 <= x0:
                continue
            if shape.alpha is None:
                allowed[x0-left:x1-left] = 255
            else:
                allowed[x0-left:x1-left] = shape.alpha[
                    y-shape.y, x0-shape.x:x1-shape.x
                ]
        if np.any(actual > allowed):
            raise ValueError('最终输出PNG进入切割安全通道')
