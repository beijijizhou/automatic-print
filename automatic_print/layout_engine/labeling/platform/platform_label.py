"""A separate readable platform badge, sized from the actual rotated QR."""
from PIL import Image

from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.labeling.platform.platform_space import card_space, header_space
from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.measurement.measurement_timing import measured
from automatic_print.layout_engine.intake.metadata.source_metadata import source_size


@measured('平台文字测量')
def platform_badge(text, target_height, degrees=0):
    from automatic_print.layout_engine.labeling.text.platform_badge import badge_data
    width, pixels = badge_data(text, target_height)
    badge = Image.frombytes('RGBA', (width, target_height), pixels)
    transpose = {
        90: Image.Transpose.ROTATE_90,
        -90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
    }.get(degrees)
    if transpose is None:
        return badge
    rotated = badge.transpose(transpose)
    badge.close()
    return rotated


@measured('平台文字测量')
def platform_badge_size(text, target_height, degrees=0):
    """Measure cached badge pixels without constructing a temporary image."""
    from automatic_print.layout_engine.labeling.text.platform_badge import badge_data
    width, _pixels = badge_data(text, target_height)
    return ((target_height, width) if degrees % 180
            else (width, target_height))


def placement_badge(text, width, height, degrees):
    """Rebuild the badge from stored final geometry without changing scale."""
    source_height = width if degrees % 180 else height
    badge = platform_badge(text, source_height, degrees)
    if badge.size != (width, height):
        badge.close()
        raise ValueError('平台尺码标签测量与输出尺寸不一致，禁止输出。')
    return badge


def platform_text(path, settings):
    """Use one per-image badge text for geometry, preview, and output."""
    size = source_size(path)
    return f'{settings.platform_name} · {size}'


def platform_geometry(path, settings, width, height, degrees):
    if not settings.platform_name or not settings.number_images:
        return 0, 0, 0, 0
    if (settings.platform_below_marker and not settings.platform_reuse_qr
            and settings.color_block_enabled and settings.platform_font_height_mm > 0):
        target = max(2, mm_to_px(settings.platform_font_height_mm, settings.dpi))
        badge_width, badge_height = platform_badge_size(
            platform_text(path, settings), target, degrees,
        )
        return 0, 0, badge_width, badge_height
    source_region = detect_guide_band(path)
    if source_region is None:
        # Preserve the source, but never invent the platform badge's geometry.
        return 0, 0, 0, 0
    source_width, source_height = (
        (height, width) if degrees % 180 else (width, height)
    )
    target = max(
        1,
        round(source_region.bottom * source_height)
        - round(source_region.top * source_height),
    )
    region = source_region.rotated(degrees)
    top = round(region.top*height)
    if settings.platform_font_height_mm > 0:
        target = min(target, max(2, mm_to_px(settings.platform_font_height_mm, settings.dpi)))
    text = platform_text(path, settings)
    badge_width, badge_height = platform_badge_size(text, target, degrees)
    gap = mm_to_px(settings.platform_gap_mm, settings.dpi)
    if settings.platform_below_marker and not settings.platform_reuse_qr and settings.color_block_enabled:
        return 0, 0, badge_width, badge_height
    # Developer mode may explicitly reuse verified QR-card space even while
    # the original header gap is preserved.
    search_header = (
        settings.platform_reuse_qr
        or not (settings.preserve_header_gap and degrees % 180 == 0)
    )
    fitted = (
        (_largest_card_badge(
            path, source_region, source_width, source_height, text, target, degrees)
         if settings.platform_reuse_qr else
         _largest_header_badge(
            path, source_region, source_width, source_height, text, target, gap, degrees))
        if search_header else None
    )
    if fitted is not None:
        return fitted
    x = None
    if x is None:
        if settings.platform_reuse_qr:
            # Missing verified space means no added badge. Never move source-label
            # content into the independent cutter-marker lane.
            return 0, 0, 0, 0
        # Never append a wide platform name to the artwork's right edge.
        x = -gap-badge_width
    return x, top, badge_width, badge_height


def _largest_card_badge(
        path, source_region, source_width, source_height,
        text, maximum_height, degrees):
    """Fit in the source QR card, then rotate the whole label with the image."""
    from automatic_print.layout_engine.measurement.measurement_session import (
        SESSION,
        identity,
    )
    session = SESSION.get()
    key = (
        'largest-card-badge', identity(path), source_region,
        source_width, source_height, text, maximum_height,
    ) if session else None
    if session and key in session.bands:
        best = session.bands[key]
        return (_rotate_rect(best, source_width, source_height, degrees)
                if best is not None else None)
    low, high, best = 2, maximum_height, None
    while low <= high:
        target = (low + high) // 2
        try:
            badge_width, badge_height = platform_badge_size(text, target)
        except ValueError:
            low = target + 1
            continue
        candidate = card_space(
            path, source_region, source_width, source_height,
            badge_width, badge_height,
        )
        if candidate is None:
            high = target - 1
        else:
            best = (candidate[0], candidate[1], badge_width, badge_height)
            low = target + 1
    if session:
        session.bands[key] = best
    return (_rotate_rect(best, source_width, source_height, degrees)
            if best is not None else None)


def _largest_header_badge(
        path, source_region, source_width, source_height,
        text, maximum_height, gap, degrees):
    """Compatibility path for labels intentionally placed beside the card."""
    low, high, best = 2, maximum_height, None
    while low <= high:
        target = (low + high) // 2
        try:
            badge_width, badge_height = platform_badge_size(text, target)
        except ValueError:
            low = target + 1
            continue
        candidate = header_space(
            path, source_region, source_width, source_height,
            badge_width, badge_height, gap, 0,
        )
        if candidate is None:
            high = target - 1
        else:
            best = _rotate_rect(
                (candidate, round(source_region.top*source_height),
                 badge_width, badge_height),
                source_width, source_height, degrees,
            )
            low = target + 1
    return best


def _rotate_rect(rect, source_width, source_height, degrees):
    """Rotate source pixel geometry exactly like the source image and QR card."""
    x, y, width, height = rect
    degrees = degrees % 360
    if degrees == 90:
        return y, source_width-x-width, height, width
    if degrees == 270:
        return source_height-y-height, x, height, width
    if degrees == 180:
        return source_width-x-width, source_height-y-height, width, height
    return x, y, width, height
