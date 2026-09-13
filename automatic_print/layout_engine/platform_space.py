"""Reuse verified transparent QR-header space without extending artwork width."""
from math import floor, ceil
from PIL import Image
from .membrane_region import MembraneRegion


def header_space(path, qr, width, height, badge_width, badge_height, gap, degrees):
    top = round(qr.top*height)
    right = ceil(qr.right*width)+gap
    left = floor(qr.left*width)-gap-badge_width
    candidates = tuple(right+step for step in range(0, max(8, badge_height), 2)) + tuple(
        left-step for step in range(0, max(8, badge_height), 2))
    with Image.open(path) as source:
        if 'A' not in source.getbands():
            return None
        for x in candidates:
            if x < 0 or x+badge_width > width or top+badge_height > height:
                continue
            region = MembraneRegion(x/width, top/height,
                (x+badge_width)/width, (top+badge_height)/height).rotated(-degrees)
            # Include resampling neighbours, not merely the glyph's black pixels.
            box = (max(0, floor(region.left*source.width)-3),
                   max(0, floor(region.top*source.height)-3),
                   min(source.width, ceil(region.right*source.width)+3),
                   min(source.height, ceil(region.bottom*source.height)+3))
            with source.crop(box) as crop:
                if crop.getchannel('A').getextrema()[1] == 0:
                    return x
    return None
