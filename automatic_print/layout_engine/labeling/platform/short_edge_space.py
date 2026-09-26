"""Verified transparency at the short end of a rotated source label card."""
from math import ceil, floor

from automatic_print.layout_engine.measurement.measurement_session import source_pixels
from automatic_print.layout_engine.measurement.measurement_timing import measured
from .transparent_search import clear_rectangles


@measured('旋转膜标签短边空位搜索')
def short_edge_space(path, card, width, height, badge_width, badge_height,
                     degrees, reserved=(), horizontal_align="left"):
    """Search inward from the card's short end, never outside source pixels."""
    if badge_width <= 0 or badge_height <= 0:
        return 0, 0
    left = ceil(card.left*width)
    right = floor(card.right*width)-badge_width
    if left > right:
        return None
    positions = {
        "left": left,
        "center": (left+right)//2,
        "right": right,
    }
    preferred = positions.get(horizontal_align, left)
    xs = tuple(dict.fromkeys((preferred, left, positions["center"], right)))
    above = (card.top+card.bottom)/2 >= .5
    edge = floor(card.top*height)-badge_height-4 if above else ceil(card.bottom*height)+4
    limit = -1 if above else height-badge_height+1
    step = -2 if above else 2
    candidates = ((x, y, badge_width, badge_height)
                  for y in range(edge, limit, step) for x in xs)
    with source_pixels(path) as source:
        batch = []
        for rect in candidates:
            x, y, w, h = rect
            if y < 0 or y+h > height or _overlaps_reserved(rect, reserved):
                continue
            batch.append(rect)
            if len(batch) >= 96:
                clear = clear_rectangles(path, width, height, degrees, batch, source=source)
                if any(clear):
                    x, y, _, _ = batch[clear.index(True)]
                    return x, y
                batch.clear()
        if batch:
            clear = clear_rectangles(path, width, height, degrees, batch, source=source)
            if any(clear):
                x, y, _, _ = batch[clear.index(True)]
                return x, y
    return None


def _overlaps_reserved(rect, reserved):
    x, y, width, height = rect
    return any(rw and rh and x < rx+rw and x+width > rx
               and y < ry+rh and y+height > ry for rx, ry, rw, rh in reserved)
