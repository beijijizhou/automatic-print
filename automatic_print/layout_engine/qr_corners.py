"""Detect only the two source header corners and restore full-source coordinates."""
from math import ceil

from .membrane_region import MembraneRegion
from .measurement_session import source_pixels
from .qr_detection import cv2, np, _detect_points


def detect_source_corners(path):
    if cv2 is None or np is None:
        return None
    with source_pixels(path) as source:
        width, height = source.size
        # Overlap around the centre avoids clipping a QR near the header midpoint.
        # The second bounded pass accommodates taller headers, never the full artwork.
        for horizontal, vertical in ((.60, .40), (.65, .75)):
            cw, ch = ceil(width*horizontal), ceil(height*vertical)
            for left in (0, width-cw):
                region = _corner(source, (left, 0, left+cw, ch))
                if region is not None:
                    return region
    return None


def _corner(source, box):
    with source.crop(box) as crop:
        longest = max(crop.size)
        scale = min(4, 400/longest) if longest < 400 else min(1, 1200/longest)
        if scale != 1:
            from PIL import Image
            small = crop.resize((max(1, round(crop.width*scale)),
                                 max(1, round(crop.height*scale))),
                                Image.Resampling.NEAREST if scale > 1 else Image.Resampling.LANCZOS)
        else:
            small = crop.copy()
        with small, small.convert('RGBA') as rgba:
            pixels = np.asarray(rgba)
            alpha = pixels[:, :, 3:4].astype(np.float32)/255
            rgb = pixels[:, :, :3]*alpha+255*(1-alpha)
            gray = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY)
            if gray.min() == gray.max():
                return None
            points = _detect_points(gray)
            if points is None:
                return None
            points = points.reshape(-1, 2)
            sx, sy = crop.width/small.width, crop.height/small.height
            left, top = np.min(points, axis=0)
            right, bottom = np.max(points, axis=0)
            return MembraneRegion(max(0, (box[0]+float(left)*sx)/source.width),
                max(0, float(top)*sy/source.height),
                min(1, (box[0]+float(right)*sx)/source.width),
                min(1, float(bottom)*sy/source.height))
