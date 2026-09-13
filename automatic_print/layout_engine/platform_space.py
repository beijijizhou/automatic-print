"""Reuse verified transparent QR-header space without extending artwork width."""
from math import floor, ceil
import numpy as np
from .membrane_region import MembraneRegion
from .measurement_session import source_pixels


def header_space(path, qr, width, height, badge_width, badge_height, gap, degrees):
    top = round(qr.top*height)
    right = ceil(qr.right*width)+gap
    left = floor(qr.left*width)-gap-badge_width
    candidates = tuple(right+step for step in range(0, max(8, badge_height), 2)) + tuple(
        left-step for step in range(0, max(8, badge_height), 2))
    with source_pixels(path) as source:
        if 'A' not in source.getbands():
            return None
        candidates += _free_band_candidates(source, qr, width, height,
                                            badge_width, badge_height, degrees)
        for x in candidates:
            if x < 0 or x+badge_width > width or top+badge_height > height:
                continue
            region = MembraneRegion(x/width, top/height,
                (x+badge_width)/width, (top+badge_height)/height).rotated((-degrees+180)%360-180)
            # Include resampling neighbours, not merely the glyph's black pixels.
            box = (max(0, floor(region.left*source.width)-3),
                   max(0, floor(region.top*source.height)-3),
                   min(source.width, ceil(region.right*source.width)+3),
                   min(source.height, ceil(region.bottom*source.height)+3))
            with source.crop(box) as crop:
                if crop.getchannel('A').getextrema()[1] == 0:
                    return x
    return None


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
