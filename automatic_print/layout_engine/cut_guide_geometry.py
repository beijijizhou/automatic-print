"""QR-height guide spans shared by the preview and printed knife dots."""
from dataclasses import dataclass
from functools import lru_cache
from math import ceil, floor
from pathlib import Path

from .membrane_region import MembraneRegion
from .models import mm_to_px
from .qr_detection import cv2, np, _detect_points


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
    raw = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if raw is None:
        return None
    scale = min(1, 1800 / max(raw.shape[:2]))
    if scale < 1:
        raw = cv2.resize(raw, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if raw.ndim == 2:
        gray = raw
    else:
        rgb = raw[:, :, :3].astype(np.float32)
        if raw.shape[2] == 4:
            alpha = raw[:, :, 3:4].astype(np.float32) / 255
            rgb = rgb*alpha + 255*(1-alpha)
        gray = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    points = _detect_points(gray)
    if points is None:
        # Isolate the source header from the artwork when whole-image detection fails.
        for fraction in (0.5, 0.3):
            points = _detect_points(gray[:max(1, round(gray.shape[0]*fraction))])
            if points is not None:
                break
    if points is None:
        return None
    points = points.reshape(-1, 2)
    height, width = gray.shape
    left, top = np.min(points, axis=0)
    right, bottom = np.max(points, axis=0)
    return MembraneRegion(max(0,float(left)/width), max(0,float(top)/height),
                          min(1,float(right)/width), min(1,float(bottom)/height))


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
