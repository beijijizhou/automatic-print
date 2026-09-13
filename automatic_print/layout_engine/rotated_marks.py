"""QR-relative rotated labels, independent of the fixed left sensor marker."""
from math import ceil

from .cut_guide_geometry import detect_guide_band
from .marker_space import transparent_rect
from .transparent_search import clear_rectangles


def rotated_marks(path, width, height, degrees, settings, block, label, platform):
    if not degrees % 360 or settings.cutter_mode == 'free':
        return None
    qr = detect_guide_band(path)
    if qr is None:
        # Keep the existing external left marker/label, without QR-relative placement.
        return None
    qr = qr.rotated(degrees)
    bx, _, bw, bh = block
    _, _, lw, lh = label
    px, py, pw, ph = platform
    by = marker_top(qr, height)
    lx = max(0, round(qr.left*width))
    ly = ceil(qr.bottom*height) + max(1, round(settings.number_gap_mm*settings.dpi/25.4))

    def clear(rect):
        x, y, w, h = rect
        return transparent_rect(path, width, height, degrees, rect) and not (
            pw and w and h and x < px+pw and x+w > px and y < py+ph and y+h > py)

    # Search only directly below the QR, never horizontally away from it.
    if lw and lh:
        positions = range(ly, height-lh+1, max(1, round(settings.dpi/25.4)))
        valid = clear_rectangles(path, width, height, degrees,
                                ((lx, y, lw, lh) for y in positions), vertical=True)
        ly = next((y for y, empty in zip(positions, valid) if empty and not (
            pw and lx < px+pw and lx+lw > px and y < py+ph and y+lh > py)),
            height + max(1, round(settings.number_gap_mm*settings.dpi/25.4)))
    # Marker origin cannot follow the QR horizontally; outside fallback is safe.
    if not (pw and px < 0) and clear((0, by, bw, bh)):
        bx = 0
    return bx, by, lx, ly


def marker_top(qr, height):
    """A bottom-left QR must not drag the cutter mark to the batch tail."""
    if (qr.left+qr.right)/2 < .5 and (qr.top+qr.bottom)/2 >= .5:
        return 0
    return max(0, round(qr.top*height))
