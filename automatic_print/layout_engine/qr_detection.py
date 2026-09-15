from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class QrLocation:
    """Normalized center point of a QR code inside an image."""

    x_ratio: float
    y_ratio: float


def detect_qr_location(path: Path) -> QrLocation | None:
    """Legacy name: return the label card centre, without QR recognition."""
    try:
        from .measurement_session import SESSION, identity
        key = identity(path)
        session = SESSION.get()
        if session is not None and key in session.qr_locations:
            return session.qr_locations[key]
        result = _detect(path)
        if session is not None:
            session.qr_locations[key] = result
        return result
    except (OSError, ValueError):
        return None


def _detect(path: Path) -> QrLocation | None:
    from .cut_guide_geometry import detect_guide_band
    region = detect_guide_band(path)
    if region is None:
        return None
    return QrLocation((region.left+region.right)/2, (region.top+region.bottom)/2)
