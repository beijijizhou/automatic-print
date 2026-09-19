"""Reuse verified transparent QR-header space without extending artwork width."""
from math import floor, ceil
import numpy as np
from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.measurement.measurement_session import source_pixels
from automatic_print.layout_engine.labeling.platform.transparent_search import clear_rectangles


from automatic_print.layout_engine.measurement.measurement_timing import measured


@measured('膜标签卡片空位搜索')
def card_space(path, card, width, height, badge_width, badge_height, reserved=()):
    """Find unprinted white/transparent pixels strictly inside the label card."""
    if badge_width <= 0 or badge_height <= 0:
        return 0, 0
    source_width, source_height, left, top, right, bottom, integral = (
        _card_integral(path, card)
    )
    box_width = max(1, ceil(badge_width*source_width/width))
    box_height = max(1, ceil(badge_height*source_height/height))
    if right-left < box_width or bottom-top < box_height:
        return None
    source_reserved = tuple(
        (floor(x*source_width/width)-left, floor(y*source_height/height)-top,
         ceil((x+w)*source_width/width)-left, ceil((y+h)*source_height/height)-top)
        for x, y, w, h in reserved if w and h
    )
    position = _first_clear_card_rect(
        integral, right-left, bottom-top, box_width, box_height, source_reserved,
    )
    if position is not None:
        x, y = position
        return (round((x+left)*width/source_width),
                round((y+top)*height/source_height))
    return None


def _first_clear_card_rect(integral, width, height, box_width, box_height, reserved):
    """Keep the original top-to-bottom, left-to-right safety search order."""
    xs = np.arange(width-box_width+1)
    for y in range(height-box_height+1):
        occupied = (integral[y+box_height, xs+box_width]
                    - integral[y, xs+box_width]
                    - integral[y+box_height, xs] + integral[y, xs])
        clear = occupied == 0
        for rx1, ry1, rx2, ry2 in reserved:
            if y < ry2 and y+box_height > ry1:
                clear &= ~((xs < rx2) & (xs+box_width > rx1))
        candidates = np.flatnonzero(clear)
        if candidates.size:
            return int(candidates[0]), y
    return None


def _card_integral(path, card):
    """Extract one source card once; badge-size probes reuse its integral image."""
    from automatic_print.layout_engine.measurement.measurement_session import (
        SESSION,
        identity,
    )
    session = SESSION.get()
    key = ('card-integral', identity(path), card) if session else None
    if session and key in session.bands:
        return session.bands[key]
    with source_pixels(path) as source:
        source_width, source_height = source.size
        left = max(0, ceil(card.left*source_width)+1)
        top = max(0, ceil(card.top*source_height)+1)
        right = min(source_width, floor(card.right*source_width)-1)
        bottom = min(source_height, floor(card.bottom*source_height)-1)
        with source.crop((left, top, right, bottom)) as card_image:
            with card_image.convert('RGBA') as rgba:
                pixels = np.asarray(rgba).copy()
    alpha = pixels[:, :, 3]
    blank = (alpha <= 15) | (
        (alpha >= 240) & (pixels[:, :, :3].min(axis=2) >= 235)
    )
    blocked = (~blank).astype(np.int32)
    result = (
        source_width, source_height, left, top, right, bottom,
        np.pad(blocked, ((1, 0), (1, 0))).cumsum(0).cumsum(1),
    )
    if session:
        session.bands[key] = result
    return result


def card_rect_clear(path, width, height, degrees, rect):
    """Validate final rotated geometry against the source label card."""
    x, y, box_width, box_height = rect
    if box_width <= 0 or box_height <= 0:
        return True
    card = MembraneRegion(x/width, y/height,
                          (x+box_width)/width, (y+box_height)/height)
    card = card.rotated((-degrees+180)%360-180)
    from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
    source_card = detect_guide_band(path)
    if source_card is None:
        return False
    tolerance = 1e-3
    if (card.left < source_card.left-tolerance or card.top < source_card.top-tolerance
            or card.right > source_card.right+tolerance
            or card.bottom > source_card.bottom+tolerance):
        return False
    with source_pixels(path) as source:
        source_width, source_height = source.size
        left = max(0, floor(card.left*source_width))
        top = max(0, floor(card.top*source_height))
        right = min(source_width, ceil(card.right*source_width))
        bottom = min(source_height, ceil(card.bottom*source_height))
        if right <= left or bottom <= top:
            return False
        with source.crop((left, top, right, bottom)) as card_image:
            with card_image.convert('RGBA') as rgba:
                crop = np.asarray(rgba).copy()
        alpha = crop[:, :, 3]
        blank = (alpha <= 15) | ((alpha >= 240) & (crop[:, :, :3].min(axis=2) >= 235))
        return bool(blank.all())


@measured('平台透明空位搜索')
def header_space(
        path, qr, width, height, badge_width, badge_height, gap, degrees,
        reserved=()):
    top = round(qr.top*height)
    right = ceil(qr.right*width)+gap
    left = floor(qr.left*width)-gap-badge_width
    candidates = tuple(right+step for step in range(0, max(8, badge_height), 2)) + tuple(
        left-step for step in range(0, max(8, badge_height), 2))
    with source_pixels(path) as source:
        if 'A' not in source.getbands():
            return None
        # Keep the exact candidate order and the source resampling padding.
        def find(options):
            options = tuple(x for x in options if not _overlaps_reserved(
                (x, top, badge_width, badge_height), reserved))
            rectangles = tuple((x, top, badge_width, badge_height) for x in options)
            clear = clear_rectangles(path, width, height, degrees, rectangles, source=source)
            return next((x for x, valid in zip(options, clear) if valid), None)
        # The known blank header usually fits the nearest position immediately.
        # Check one rectangle before building/scanning every shifted candidate.
        found = find(candidates[:1])
        if found is None:
            found = find(candidates[1:])
        if found is not None:
            return found
        return find(_free_band_candidates(source, qr, width, height,
                                         badge_width, badge_height, degrees))
    return None


def _overlaps_reserved(rect, reserved):
    x, y, width, height = rect
    return any(
        rw and rh and x < rx+rw and x+width > rx and y < ry+rh and y+height > ry
        for rx, ry, rw, rh in reserved
    )


def _free_band_candidates(source, qr, width, height, badge_width, badge_height, degrees):
    """Search the complete header, including space beyond a long label card."""
    top = round(qr.top*height)
    band = MembraneRegion(0, top/height, 1, (top+badge_height)/height).rotated((-degrees+180)%360-180)
    box = (floor(band.left*source.width), floor(band.top*source.height),
           ceil(band.right*source.width), ceil(band.bottom*source.height))
    with source.crop(box) as crop:
        alpha = crop.getchannel('A').rotate(degrees, expand=True)
        occupied = np.asarray(alpha).max(axis=0) > 0
        scale = width / alpha.width
        alpha.close()
    edges = np.flatnonzero(np.diff(np.r_[True, occupied, True].astype(np.int8)))
    candidates = []
    for start, end in zip(edges[::2], edges[1::2]):
        left, right = ceil((start+4)*scale), floor((end-4)*scale)-badge_width
        if left <= right:
            candidates.extend((left, right))
    center = (qr.left+qr.right)*width/2
    return tuple(sorted(set(candidates), key=lambda x: abs(x+badge_width/2-center)))
