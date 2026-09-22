"""Search verified transparent space outside the source label card."""
from math import floor, ceil
import numpy as np
from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.measurement.measurement_session import source_pixels
from automatic_print.layout_engine.labeling.platform.transparent_search import clear_rectangles


from automatic_print.layout_engine.measurement.measurement_timing import measured


@measured('平台透明空位搜索')
def header_space(
        path, qr, width, height, badge_width, badge_height, gap, degrees,
        reserved=(), inward_from_card=False):
    top = round(qr.top*height)
    right = ceil(qr.right*width)+gap
    left = floor(qr.left*width)-gap-badge_width
    left_candidates = tuple(left-step for step in range(0, max(8, badge_height), 2))
    right_candidates = tuple(right+step for step in range(0, max(8, badge_height), 2))
    card_on_left = (qr.left+qr.right)/2 < .5
    if inward_from_card and card_on_left:
        right_candidates += tuple(
            rx+rw+step for rx, ry, rw, rh in reserved
            if rw and rh and ry < top+badge_height and ry+rh > top
            for step in range(2, max(10, badge_height+2), 2)
        )
    elif inward_from_card:
        left_candidates += tuple(
            rx-badge_width-step for rx, ry, rw, rh in reserved
            if rw and rh and ry < top+badge_height and ry+rh > top
            for step in range(2, max(10, badge_height+2), 2)
        )
    candidates = ((right_candidates if card_on_left else left_candidates)
                  if inward_from_card else right_candidates+left_candidates)
    with source_pixels(path) as source:
        if 'A' not in source.getbands():
            return None
        # Keep the exact candidate order and the source resampling padding.
        def find(options):
            options = tuple(x for x in options if (
                (not inward_from_card or (
                    ceil(qr.right*width) <= x and x+badge_width <= width
                    if card_on_left else 0 <= x and x+badge_width <= floor(qr.left*width)
                ))
                and not _overlaps_reserved(
                    (x, top, badge_width, badge_height), reserved)))
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
