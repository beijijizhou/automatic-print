"""Place added text in verified blank paper beside the real QR code."""
from math import ceil, floor

import numpy as np

from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.labeling.platform.qr_region import detect_qr_region
from automatic_print.layout_engine.measurement.measurement_session import (
    SESSION, identity, source_pixels,
)
from automatic_print.layout_engine.measurement.measurement_timing import measured


@measured('二维码同行空白搜索')
def qr_row_space(path, card, width, height, badge_width, badge_height, degrees,
                 reserved=()):
    """Find blank label-card paper beside the QR and return final coordinates."""
    qr = detect_qr_region(path)
    if qr is None or badge_width <= 0 or badge_height <= 0:
        return None
    source_width, source_height = ((height, width) if degrees % 180 else (width, height))
    source_badge_width, source_badge_height = (
        (badge_height, badge_width) if degrees % 180 else (badge_width, badge_height)
    )
    gap = max(1, round(min(
        (qr.right-qr.left)*source_width,
        (qr.bottom-qr.top)*source_height,
    ) * .04))
    card_left, card_right = ceil(card.left*source_width), floor(card.right*source_width)
    card_top, card_bottom = ceil(card.top*source_height), floor(card.bottom*source_height)
    qr_left, qr_right = floor(qr.left*source_width), ceil(qr.right*source_width)
    qr_top, qr_bottom = floor(qr.top*source_height), ceil(qr.bottom*source_height)
    y_min, y_max = card_top, card_bottom-source_badge_height
    if y_min > y_max:
        return None
    center_y = round((qr_top+qr_bottom-source_badge_height)/2)
    ys = _nearby(center_y, y_min, y_max)
    ranges = (
        (qr_right+gap, card_right-source_badge_width, qr_right+gap),
        (card_left, qr_left-gap-source_badge_width, qr_left-gap-source_badge_width),
    )
    ranges = sorted(ranges, key=lambda value: value[1]-value[0], reverse=True)
    candidates = []
    for start, end, near_qr in ranges:
        if start > end:
            continue
        xs = tuple(dict.fromkeys((near_qr, start, end, (start+end)//2)))
        candidates.extend((x, y, source_badge_width, source_badge_height)
                          for y in ys for x in xs if start <= x <= end)
    with source_pixels(path) as source:
        for source_rect in candidates:
            final_rect = _rotate_rect(source_rect, source_width, source_height, degrees)
            if _overlaps_reserved(final_rect, reserved):
                continue
            if _blank_card_pixels(
                    source, source_rect, source_width, source_height):
                return final_rect[:2]
    return None


def is_qr_row_space(path, width, height, degrees, rect):
    """Recheck that a final rectangle uses blank card paper beside the QR."""
    session = SESSION.get()
    key = (identity(path), width, height, degrees, tuple(rect)) if session else None
    if session is not None and key in session.qr_row_rectangles:
        return session.qr_row_rectangles[key]
    result = _is_qr_row_space(path, width, height, degrees, rect)
    if session is not None:
        session.qr_row_rectangles[key] = result
    return result


def _is_qr_row_space(path, width, height, degrees, rect):
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return True
    source_width, source_height = ((height, width) if degrees % 180 else (width, height))
    source_rect = _rotate_rect((x, y, w, h), width, height, -degrees)
    sx, sy, sw, sh = source_rect
    from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
    card, qr = detect_guide_band(path), detect_qr_region(path)
    if card is None or qr is None:
        return False
    gap = max(1, round(min(
        (qr.right-qr.left)*source_width,
        (qr.bottom-qr.top)*source_height,
    ) * .04))
    card_box = (ceil(card.left*source_width), ceil(card.top*source_height),
                floor(card.right*source_width), floor(card.bottom*source_height))
    qr_box = (floor(qr.left*source_width), floor(qr.top*source_height),
              ceil(qr.right*source_width), ceil(qr.bottom*source_height))
    inside = (card_box[0] <= sx and sy >= card_box[1]
              and sx+sw <= card_box[2] and sy+sh <= card_box[3])
    beside = sx+sw <= qr_box[0]-gap or sx >= qr_box[2]+gap
    same_row = sy < qr_box[3] and sy+sh > qr_box[1]
    if not (inside and beside and same_row):
        return False
    with source_pixels(path) as source:
        return _blank_card_pixels(
            source, source_rect, source_width, source_height)


def _nearby(preferred, minimum, maximum):
    preferred = min(maximum, max(minimum, preferred))
    return tuple(dict.fromkeys((preferred, minimum, maximum, (minimum+maximum)//2)))


def _blank_card_pixels(source, rect, coordinate_width=None, coordinate_height=None):
    x, y, width, height = rect
    coordinate_width = coordinate_width or source.width
    coordinate_height = coordinate_height or source.height
    if (x < 0 or y < 0 or x+width > coordinate_width
            or y+height > coordinate_height):
        return False
    box = (
        floor(x/coordinate_width*source.width),
        floor(y/coordinate_height*source.height),
        ceil((x+width)/coordinate_width*source.width),
        ceil((y+height)/coordinate_height*source.height),
    )
    with source.crop(box).convert('RGBA') as crop:
        pixels = np.asarray(crop)
    alpha = pixels[:, :, 3]
    light_paper = (alpha >= 240) & (pixels[:, :, :3].min(axis=2) >= 220)
    return bool(np.all((alpha == 0) | light_paper))


def _rotate_rect(rect, width, height, degrees):
    x, y, rect_width, rect_height = rect
    degrees %= 360
    if degrees == 90:
        return y, width-x-rect_width, rect_height, rect_width
    if degrees == 270:
        return height-y-rect_height, x, rect_height, rect_width
    if degrees == 180:
        return width-x-rect_width, height-y-rect_height, rect_width, rect_height
    return x, y, rect_width, rect_height


def _overlaps_reserved(rect, reserved):
    x, y, width, height = rect
    return any(rw and rh and x < rx+rw and x+width > rx
               and y < ry+rh and y+height > ry for rx, ry, rw, rh in reserved)
