"""QR-height guide spans shared by the preview and printed knife dots."""
from dataclasses import dataclass
from functools import lru_cache
from math import ceil, floor
from pathlib import Path

from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.measurement.measurement_session import identity, SESSION


@dataclass(frozen=True)
class GuideSpan:
    knife_x: int
    top: int
    bottom: int


def detect_guide_band(path: Path):
    """Legacy name: return the preferred label card band, without QR recognition."""
    try:
        key = identity(path)
        session = SESSION.get()
        if session is not None and key in session.bands:
            return session.bands[key]
        band = _cached(str(path), key[1], key[2])
        if session is not None:
            session.bands[key] = band
        return band
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=512)
def _cached(path, _mtime, _size):
    from automatic_print.layout_engine.labeling.base.header_region import search_header
    return search_header(Path(path))


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
        if top < bottom:
            # The completed plan is the sole source of truth for vertical
            # knives.  A one-column zone intentionally has no vertical knife;
            # falling back to the configured default here draws guide dots
            # through printable pixels in rotated single-column zones.
            knives = p.cut_knife_xs_px or ((p.cut_knife_x_px,)
                if p.cut_knife_x_px is not None else ())
            spans.extend(GuideSpan(knife, top, bottom) for knife in knives)
    return spans
