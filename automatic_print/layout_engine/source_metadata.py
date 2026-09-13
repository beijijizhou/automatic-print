"""Filename facts and geometric hints; hints never replace measured cut safety."""
import re

from .order_groups import production_stem, _size_rank


def canonical_size(value):
    value = value.upper().strip()
    if re.fullmatch(r'X{2,}L', value):
        return f'{len(value)-1}XL'
    match = re.fullmatch(r'(\d+)XL', value)
    if match:
        return 'XL' if int(match[1]) == 1 else f'{int(match[1])}XL'
    return value


def source_size(path):
    parts = production_stem(path).split('-')
    if len(parts) >= 5 and re.fullmatch(r'no\d+', parts[-2]):
        value = parts[-3]
        if _size_rank(value) < 1000 or re.fullmatch(r'\d+(?:\.\d+)?', value):
            return canonical_size(value)
    return '未识别尺码'


def size_key(size):
    rank = _size_rank(size.casefold())
    return rank, float(size) if size.replace('.', '', 1).isdigit() else 0, size


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
