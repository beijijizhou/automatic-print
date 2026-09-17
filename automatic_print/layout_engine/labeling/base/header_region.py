"""Locate opaque light label cards in preferred top corners, without QR detection."""
from functools import lru_cache
from pathlib import Path
import sqlite3
import numpy as np
from PIL import Image

from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.measurement.measurement_timing import measured, substep


def search_header(path):
    try:
        stat = path.stat()
        return _cached(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=4096)
@measured('膜标签卡片定位')
def _cached(path, _mtime, _size):
    persistent, persistent_key = _persistent_region_cache(path, _mtime, _size)
    if persistent is not None:
        try:
            cached = persistent.load('header_region', persistent_key)
            if cached is not None:
                values = cached.get('region')
                return MembraneRegion(*values) if values else None
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            persistent = persistent_key = None
    pixels, source_width, source_height, header_height = _header_pixels(Path(path))
    white = (pixels[:, :, 3] >= 240) & (pixels[:, :, :3].min(axis=2) >= 220)
    candidates = _cards(white)
    result = None
    if candidates:
        sample_height, sample_width = white.shape
        left, top, right, bottom = min(candidates, key=lambda r:
            (r[1], -(r[2]-r[0])*(r[3]-r[1]), min(r[0], sample_width-r[2])))
        result = MembraneRegion(
            left/sample_width, top/sample_height*header_height/source_height,
            right/sample_width, bottom/sample_height*header_height/source_height,
        )
    if persistent is not None:
        try:
            persistent.save(
                'header_region', persistent_key,
                {'region': ([result.left, result.top, result.right, result.bottom]
                            if result else None)},
            )
        except (OSError, ValueError, TypeError, sqlite3.Error):
            pass
    return result


def _persistent_region_cache(path, mtime, size):
    """Reuse one file fingerprint without opening SQLite for standalone probes."""
    try:
        from automatic_print.layout_engine.measurement.measurement_session import (
            SESSION, persistent_cache,
        )
        if SESSION.get() is None:
            return None, None
        from automatic_print.layout_engine.measurement.measurement_cache import (
            header_region_key,
        )
        identity = (str(Path(path).resolve()), mtime, size)
        return persistent_cache(), header_region_key(identity)
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return None, None


def _header_pixels(path):
    """Decode only the bounded top label strip when libvips is available."""
    from automatic_print.layout_engine.measurement.measurement_session import (
        active_source,
        source_pixels,
    )
    if active_source(path) is not None:
        with source_pixels(path) as source:
            return _pillow_header_pixels_from_source(source)
    try:
        import pyvips
    except (ImportError, OSError):
        return _pillow_header_pixels(path)
    from automatic_print.layout_engine.rendering.engines.vips_renderer import demand_lock
    with substep('顶部标签条带读取与解压'):
        with demand_lock:
            return _vips_header_pixels(path, pyvips)


def _vips_header_pixels(path, pyvips):
    source = pyvips.Image.new_from_file(str(path), access='sequential')
    source_width, source_height = source.width, source.height
    header_height = min(source_height, max(96, round(source_width*.5)))
    strip = source.crop(0, 0, source_width, header_height)
    scale = min(1.0, 1000/max(strip.width, strip.height))
    if scale < 1:
        strip = strip.resize(scale, kernel='nearest')
    if strip.format != 'uchar':
        strip = strip.cast('uchar')
    if strip.bands == 1:
        grey = strip[0]
        strip = grey.bandjoin([grey, grey, 255])
    elif strip.bands == 2:
        grey = strip[0]
        strip = grey.bandjoin([grey, grey, strip[1]])
    elif strip.bands == 3:
        strip = strip.bandjoin(255)
    elif strip.bands > 4:
        strip = strip.extract_band(0, n=4)
    pixels = np.frombuffer(strip.write_to_memory(), dtype=np.uint8)
    return pixels.reshape(strip.height, strip.width, 4), source_width, source_height, header_height


def _pillow_header_pixels(path):
    with substep('源图片像素读取与解压'), Image.open(path) as source:
        source.load()
        return _pillow_header_pixels_from_source(source)


def _pillow_header_pixels_from_source(source):
    source_width, source_height = source.size
    header_height = min(source_height, max(96, round(source_width*.5)))
    with source.crop((0, 0, source_width, header_height)) as crop:
        crop.thumbnail((1000, 1000), Image.Resampling.NEAREST)
        with crop.convert('RGBA') as rgba:
            return np.asarray(rgba).copy(), source_width, source_height, header_height


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
    return _merge_vertical_sections(merged, w, h)


def _merge_vertical_sections(boxes, width, height):
    """Rejoin one corner card split into stacked white sections by printed rules."""
    boxes = list(boxes)
    changed = True
    while changed:
        changed = False
        for first in range(len(boxes)):
            for second in range(first + 1, len(boxes)):
                a, b = boxes[first], boxes[second]
                upper, lower = (a, b) if a[1] <= b[1] else (b, a)
                upper_width, lower_width = upper[2] - upper[0], lower[2] - lower[0]
                narrow = min(upper_width, lower_width)
                overlap = min(upper[2], lower[2]) - max(upper[0], lower[0])
                gap = lower[1] - upper[3]
                same_corner = ((upper[0] < width * .4 and lower[0] < width * .4)
                               or (upper[2] > width * .6 and lower[2] > width * .6))
                combined_height = max(upper[3], lower[3]) - min(upper[1], lower[1])
                # The sampled strip is only half an image-width tall. On narrow or
                # short artwork a normal label can occupy most of that strip, so a
                # strip-height limit rejects the real lower half of the card. Card
                # geometry is stable relative to image width instead.
                if (same_corner and 0 <= gap <= max(3, round(narrow * .03))
                        and overlap >= narrow * .6 and combined_height <= width * .4):
                    boxes[first] = (
                        min(a[0], b[0]), min(a[1], b[1]),
                        max(a[2], b[2]), max(a[3], b[3]),
                    )
                    boxes.pop(second)
                    changed = True
                    break
            if changed:
                break
    return boxes


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
