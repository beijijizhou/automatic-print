"""Locate opaque light label cards in preferred top corners, without QR detection."""
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image

from .measurement_session import source_pixels
from .membrane_region import MembraneRegion


def search_header(path):
    try:
        stat = path.stat()
        return _cached(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=4096)
def _cached(path, _mtime, _size):
    with source_pixels(Path(path)) as source:
        # Width-based height keeps short source images' header cards intact.
        height = min(source.height, max(96, round(source.width*.5)))
        with source.crop((0, 0, source.width, height)) as crop:
            crop.thumbnail((1000, 1000), Image.Resampling.NEAREST)
            with crop.convert('RGBA') as rgba:
                pixels = np.asarray(rgba)
                white = (pixels[:, :, 3] >= 240) & (pixels[:, :, :3].min(axis=2) >= 220)
            candidates = _cards(white)
            if not candidates:
                return None
            left, top, right, bottom = min(candidates, key=lambda r:
                (r[1], -(r[2]-r[0])*(r[3]-r[1]), min(r[0], crop.width-r[2])))
            return MembraneRegion(left/crop.width, top/crop.height*height/source.height,
                                  right/crop.width, bottom/crop.height*height/source.height)


def _cards(white):
    # Connected light paper survives printed text/invalid codes; transparent pixels
    # never count as white paper. OpenCV is only an optional component-labeling backend.
    try:
        import cv2
        count, _, stats, _ = cv2.connectedComponentsWithStats(white.astype('uint8'), connectivity=8)
        boxes = [(int(x), int(y), int(x+w), int(y+h), int(area))
                 for x, y, w, h, area in stats[1:count]]
    except ImportError:
        boxes = _components(white)
    h, w = white.shape
    candidates = []
    for left, top, right, bottom, area in boxes:
        bw, bh = right-left, bottom-top
        if bw < 8 or bh < 8 or bw < bh*.4 or area < 40 or area < bw*bh*.25:
            continue
        if top > h*.35 or not (left < w*.4 or right > w*.6):
            continue
        # No isolated card on a completely light/opaque sheet: do not guess a band.
        if left == 0 and right == w and bottom == h:
            continue
        if bottom == h and top > 0:
            continue
        candidates.append((left, top, right, bottom))
    merged = []
    for box in sorted(candidates, key=lambda r: r[0]):
        if merged:
            a = merged[-1]
            overlap = min(a[3], box[3])-max(a[1], box[1])
            short = min(a[3]-a[1], box[3]-box[1])
            if overlap >= short*.75 and box[0]-a[2] <= max(3, short*.12):
                merged[-1] = (a[0], min(a[1], box[1]), max(a[2], box[2]), max(a[3], box[3]))
                continue
        merged.append(box)
    return merged


def _components(mask):
    """Bounded fallback using horizontal runs, not a per-pixel Python flood fill."""
    groups, parents, previous = [], [], []
    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    for y, row in enumerate(mask):
        edges = np.flatnonzero(np.diff(np.r_[False, row, False].astype('int8')))
        current = []
        for left, right in zip(edges[::2], edges[1::2]):
            linked = {root(g) for a, b, g in previous if a <= right and b >= left}
            if linked:
                index = min(linked)
                group = groups[index]
                for other in linked-{index}:
                    parents[other] = index
                    box = groups[other]
                    group[0] = min(group[0], box[0])
                    group[1] = min(group[1], box[1])
                    group[2] = max(group[2], box[2])
                    group[4] += box[4]
                group[0] = min(group[0], int(left)); group[2] = max(group[2], int(right))
                group[3] = y+1; group[4] += int(right-left)
            else:
                index = len(groups)
                parents.append(index)
                group = [int(left), y, int(right), y+1, int(right-left)]
                groups.append(group)
            current.append((left, right, index))
        previous = current
    return [group for index, group in enumerate(groups) if root(index) == index]
