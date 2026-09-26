"""Detect the real QR bounds inside the source membrane label card."""
from functools import lru_cache
from math import ceil, floor

import numpy as np

from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.measurement.measurement_session import (
    SESSION, identity, source_pixels,
)
from automatic_print.layout_engine.measurement.measurement_timing import measured


def detect_qr_region(path):
    """Return normalized source QR bounds, or ``None`` when detection is unsafe."""
    session = SESSION.get()
    if session is not None:
        key = identity(path)
        if key not in session.qr_regions:
            session.qr_regions[key] = _detect(path)
        return session.qr_regions[key]
    try:
        stat = path.stat()
        return _cached(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=4096)
def _cached(path, _mtime, _size):
    from pathlib import Path
    return _detect(Path(path))


@measured('膜标签二维码定位')
def _detect(path):
    from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
    card = detect_guide_band(path)
    if card is None:
        return None
    try:
        import cv2
    except (ImportError, OSError):
        return None
    with source_pixels(path) as source:
        source_width, source_height = source.size
        left = max(0, floor(card.left * source.width))
        top = max(0, floor(card.top * source.height))
        right = min(source.width, ceil(card.right * source.width))
        bottom = min(source.height, ceil(card.bottom * source.height))
        if right-left < 8 or bottom-top < 8:
            return None
        with source.crop((left, top, right, bottom)).convert('RGBA') as crop:
            pixels = np.asarray(crop).copy()
    alpha = pixels[:, :, 3]
    rgb = pixels[:, :, :3]
    rgb[alpha == 0] = 255
    scale = max(1, ceil(160 / min(rgb.shape[:2])))
    if scale > 1:
        rgb = cv2.resize(rgb, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_NEAREST)
    try:
        found, points = cv2.QRCodeDetector().detect(rgb)
    except cv2.error:
        return None
    if not found or points is None:
        return None
    points = points.reshape(-1, 2) / scale
    qr_left, qr_top = points.min(axis=0)
    qr_right, qr_bottom = points.max(axis=0)
    qr_width, qr_height = qr_right-qr_left, qr_bottom-qr_top
    if min(qr_width, qr_height) < 5 or max(qr_width, qr_height) > min(
            right-left, bottom-top) * 1.2:
        return None
    return MembraneRegion(
        (left+qr_left)/source_width,
        (top+qr_top)/source_height,
        (left+qr_right+1)/source_width,
        (top+qr_bottom+1)/source_height,
    )
