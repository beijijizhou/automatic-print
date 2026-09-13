"""Preferred label card bounds and legacy ink-band geometry helpers."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class MembraneRegion:
    left: float
    top: float
    right: float
    bottom: float

    def rotated(self, degrees):
        if degrees == 90:
            return MembraneRegion(self.top, 1-self.right, self.bottom, 1-self.left)
        if degrees in {-90, 270}:
            return MembraneRegion(1-self.bottom, self.left, 1-self.top, self.right)
        if degrees in {180, -180}:
            return MembraneRegion(1-self.right, 1-self.bottom, 1-self.left, 1-self.top)
        return self


def detect_membrane_region(path: Path):
    try:
        stat = path.stat()
        return _cached(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=4096)
def _cached(path, _mtime, _size):
    from .header_region import search_header
    return search_header(Path(path))


def region_from_ink(ink, points):
    """Require an isolated horizontal ink band containing the entire QR."""
    height, width = ink.shape
    points = points.reshape(-1, 2)
    qr_top = max(0, int(points[:, 1].min()))
    qr_bottom = min(height-1, int(np.ceil(points[:, 1].max())))
    occupied = ink.any(axis=1)
    top, bottom = qr_top, qr_bottom
    blank = max(2, round((qr_bottom-qr_top) * 0.06))
    while top > blank and occupied[top-blank:top].any():
        top -= 1
    while bottom < height-blank-1 and occupied[bottom+1:bottom+blank+1].any():
        bottom += 1
    # If connected to the artwork, do not pretend its height is a label height.
    if bottom-top > (qr_bottom-qr_top+1) * 3 or bottom-top > height * 0.35:
        return None
    ys, xs = np.nonzero(ink[top:bottom+1])
    if not len(xs):
        return None
    return MembraneRegion(xs.min()/width, top/height, (xs.max()+1)/width, (bottom+1)/height)
