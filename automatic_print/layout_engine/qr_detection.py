from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None


@dataclass(frozen=True)
class QrLocation:
    """Normalized center point of a QR code inside an image."""

    x_ratio: float
    y_ratio: float


def detect_qr_location(path: Path) -> QrLocation | None:
    """Find a QR position without decoding or retaining the source image."""
    if cv2 is None or np is None:
        return None
    try:
        stat = path.stat()
        return _detect_cached(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, cv2.error):
        return None


@lru_cache(maxsize=4096)
def _detect_cached(
    path: str, _modified_ns: int, _file_size: int
) -> QrLocation | None:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None or not image.size:
        return None
    image = _scaled_for_detection(image)
    points = _detect_points(image)
    if points is None:
        return None
    height, width = image.shape[:2]
    center = points.reshape(-1, 2).mean(axis=0)
    return QrLocation(
        min(1.0, max(0.0, float(center[0]) / width)),
        min(1.0, max(0.0, float(center[1]) / height)),
    )


def _scaled_for_detection(image, maximum: int = 1800):
    height, width = image.shape[:2]
    largest = max(width, height)
    if largest <= maximum:
        return image
    scale = maximum / largest
    return cv2.resize(
        image,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _detect_points(image):
    detector = cv2.QRCodeDetector()
    try:
        found, groups = detector.detectMulti(image)
        if found and groups is not None and len(groups):
            return max(groups, key=_polygon_area)
    except (AttributeError, cv2.error):
        pass
    found, points = detector.detect(image)
    return points if found else None


def _polygon_area(points) -> float:
    return abs(float(cv2.contourArea(points.astype(np.float32))))
