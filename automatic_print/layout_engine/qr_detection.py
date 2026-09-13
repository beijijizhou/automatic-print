from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

@dataclass(frozen=True)
class QrLocation:
    """Normalized center point of a QR code inside an image."""

    x_ratio: float
    y_ratio: float


def detect_qr_location(path: Path) -> QrLocation | None:
    """Legacy name: return the label card centre, without QR recognition."""
    try:
        stat = path.stat()
        return _detect_cached(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=4096)
def _detect_cached(
    path: str, _modified_ns: int, _file_size: int
) -> QrLocation | None:
    from .cut_guide_geometry import detect_guide_band
    region = detect_guide_band(Path(path))
    if region is None:
        return None
    return QrLocation((region.left+region.right)/2, (region.top+region.bottom)/2)
