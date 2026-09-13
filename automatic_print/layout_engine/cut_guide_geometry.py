"""QR-height guide spans shared by the preview and printed knife dots."""
from dataclasses import dataclass
from functools import lru_cache
from math import ceil, floor
from pathlib import Path

from .membrane_region import MembraneRegion
from .models import mm_to_px
from .qr_detection import cv2, np


@dataclass(frozen=True)
class GuideSpan:
    knife_x: int
    top: int
    bottom: int


def detect_guide_band(path: Path):
    """Measure the QR's bounding box, never infer a default header height."""
    if cv2 is None or np is None:
        return None
    try:
        stat = path.stat()
        return _cached(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, cv2.error):
        return None


@lru_cache(maxsize=512)
def _cached(path, _mtime, _size):
    from .qr_corners import detect_source_corners
    return detect_source_corners(Path(path))


def guide_spans(planned, settings, bands):
    """Intersect QR-height bands across every image sharing a horizontal row."""
    rows = {}
    for path, placement in planned:
        rows.setdefault((placement.cut_zone, placement.y_px), []).append((path, placement))
    spans = []
    for members in rows.values():
        if any(bands.get(path) is None for path, _ in members):
            continue
        tops, bottoms = [], []
        for path, p in members:
            band = bands[path].rotated(p.rotation_degrees)
            tops.append(ceil(p.y_px + band.top*p.height_px))
            bottoms.append(floor(p.y_px + band.bottom*p.height_px))
        top, bottom = max(tops), min(bottoms)
        p = members[0][1]
        knife = p.cut_knife_x_px
        if knife is None:
            knife = mm_to_px(settings.cutter_knife_mm, settings.dpi)
        if top < bottom:
            spans.append(GuideSpan(knife, top, bottom))
    return spans
