"""Filename facts and geometric hints; hints never replace measured cut safety."""
import re
from functools import lru_cache

from automatic_print.layout_engine.orders.order_groups import production_stem, _size_rank


def canonical_size(value):
    value = value.upper().strip()
    if re.fullmatch(r'X{2,}L', value):
        return f'{len(value)-1}XL'
    match = re.fullmatch(r'(\d+)XL', value)
    if match:
        return 'XL' if int(match[1]) == 1 else f'{int(match[1])}XL'
    return value


@lru_cache(maxsize=4096)
def source_size(path):
    parts = production_stem(path).split('-')
    if len(parts) >= 5 and re.fullmatch(r'no\d+', parts[-2]):
        value = parts[-3]
        if _size_rank(value) < 1000 or re.fullmatch(r'\d+(?:\.\d+)?', value):
            return canonical_size(value)
    from .platform_detection import is_size_name
    if is_size_name(path.parent.name):
        return canonical_size(path.parent.name)
    return '未识别尺码'


def size_key(size):
    rank = _size_rank(size.casefold())
    return rank, float(size) if size.replace('.', '', 1).isdigit() else 0, size


@lru_cache(maxsize=4096)
def source_color(path):
    from automatic_print.automation.api.s2b.metadata.store import color_for_path
    api_color = color_for_path(path)
    if api_color:
        return api_color
    parts = production_stem(path).split('-')
    if len(parts) < 6 or not re.fullmatch(r'no\d+',parts[-2]):
        return '未识别颜色'
    color = parts[-4].strip()
    return {'black':'黑色','黑':'黑色','黑色':'黑色',
            'white':'白色','白':'白色','白色':'白色'}.get(color,color or '未识别颜色')


def color_key(color):
    return {'黑色':0,'白色':1,'未识别颜色':3}.get(color,2),color


def source_block(path):
    return source_color(path),source_size(path)


def block_key(block):
    return color_key(block[0]),size_key(block[1])


def shape_hints(width_mm, height_mm):
    hints = []
    if height_mm >= width_mm*2:
        hints.append('竖向细长图')
    elif width_mm >= height_mm*2:
        hints.append('横向细长图')
    if width_mm <= 150 and height_mm <= 200:
        hints.append('小幅图')
    return hints


def is_small_item(item, dpi):
    # Include the full marker/label footprint when selecting a companion.
    return item.footprint_width*25.4/dpi <= 165 and item.footprint_height*25.4/dpi <= 220
