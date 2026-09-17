"""A separate readable platform badge, sized from the actual rotated QR."""
from PIL import Image, ImageDraw, ImageFont
from functools import lru_cache

from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.labeling.platform.platform_space import card_space, header_space
from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.measurement.measurement_timing import measured
from automatic_print.layout_engine.intake.metadata.source_metadata import source_size


def _font(size):
    for path in ('C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/simhei.ttf',
                 '/System/Library/Fonts/Supplemental/Songti.ttc',
                 '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    raise ValueError('未找到中文字体，无法清晰打印平台名称。请安装微软雅黑或思源黑体。')


@measured('平台文字测量')
def platform_badge(text, target_height, degrees=0):
    width, pixels = _badge_data(text, target_height)
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


@lru_cache(maxsize=64)
def _badge_data(text, target_height):
    # Cache immutable pixels, never share a font face or mutable image across workers.
    if target_height < 2:
        raise ValueError('膜标签打印高度太小，无法显示可读的平台名称。')
    measure = ImageDraw.Draw(Image.new('L', (1, 1)))
    low, high, best = 1, target_height*3, None
    while low <= high:
        size = (low+high)//2
        font = _font(size)
        box = measure.textbbox((0, 0), text, font=font, stroke_width=1)
        if box[3]-box[1] <= target_height:
            best = font, box
            low = size+1
        else:
            high = size-1
    if best is None:
        raise ValueError('膜标签高度不足以容纳平台名称。')
    font, box = best
    badge = Image.new('RGBA', (box[2]-box[0], target_height))
    ImageDraw.Draw(badge).text((-box[0], (target_height-(box[3]-box[1]))//2-box[1]),
                               text, font=font, fill='black', stroke_width=1)
    pixels = badge.tobytes()
    width = badge.width
    badge.close()
    return width, pixels


def platform_geometry(path, settings, width, height, degrees):
    if not settings.platform_name or not settings.number_images:
        return 0, 0, 0, 0
    if (settings.platform_below_marker and not settings.platform_reuse_qr
            and settings.color_block_enabled and settings.platform_font_height_mm > 0):
        target = max(2, mm_to_px(settings.platform_font_height_mm, settings.dpi))
        badge = platform_badge(platform_text(path, settings), target, degrees)
        badge_width, badge_height = badge.size
        badge.close()
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
    badge = platform_badge(text, target, degrees)
    badge_width, badge_height = badge.size
    badge.close()
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
    low, high, best = 2, maximum_height, None
    while low <= high:
        target = (low + high) // 2
        try:
            badge = platform_badge(text, target)
        except ValueError:
            low = target + 1
            continue
        badge_width, badge_height = badge.size
        badge.close()
        candidate = card_space(
            path, source_region, source_width, source_height,
            badge_width, badge_height,
        )
        if candidate is None:
            high = target - 1
        else:
            best = _rotate_rect(
                (candidate[0], candidate[1],
                 badge_width, badge_height),
                source_width, source_height, degrees,
            )
            low = target + 1
    return best


def _largest_header_badge(
        path, source_region, source_width, source_height,
        text, maximum_height, gap, degrees):
    """Compatibility path for labels intentionally placed beside the card."""
    low, high, best = 2, maximum_height, None
    while low <= high:
        target = (low + high) // 2
        try:
            badge = platform_badge(text, target)
        except ValueError:
            low = target + 1
            continue
        badge_width, badge_height = badge.size
        badge.close()
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


def numbered_template(settings):
    template = settings.label_text_template
    if settings.label_source_order_enabled:
        template = source_order_template(template)
    if settings.label_machine_enabled and not any(token in template for token in ('{机器号}', '{machine}')):
        template = (template.strip()+' {机器号}').strip()
    if settings.label_sequence_enabled and not any(token in template for token in ('{编号}', '{number}')):
        template = (template.strip()+' {编号}').strip()
    return template


def source_order_template(template):
    if not any(token in template for token in ('{批次}', '{文件夹}', '{batch}')):
        template = (template.strip()+' {批次}').strip()
    return (template.strip()+' · 正序 {编号}/{总数} · 倒序 {倒序}/{总数}').strip()
