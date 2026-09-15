"""A separate readable platform badge, sized from the actual rotated QR."""
from PIL import Image, ImageDraw, ImageFont
from functools import lru_cache

from .cut_guide_geometry import detect_guide_band
from .models import mm_to_px
from .platform_space import header_space
from .membrane_region import MembraneRegion
from .measurement_timing import measured


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
def platform_badge(text, target_height):
    width, pixels = _badge_data(text, target_height)
    return Image.frombytes('RGBA', (width, target_height), pixels)


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
        badge = platform_badge(settings.platform_name, target)
        badge_width = badge.width
        badge.close()
        return 0, 0, badge_width, target
    region = detect_guide_band(path)
    if region is None:
        # Preserve the source, but never invent the platform badge's geometry.
        return 0, 0, 0, 0
    region = region.rotated(degrees)
    top = round(region.top*height)
    target = max(1, round(region.bottom*height)-top)
    if settings.platform_font_height_mm > 0:
        target = min(target, max(2, mm_to_px(settings.platform_font_height_mm, settings.dpi)))
    region = MembraneRegion(region.left, top/height, region.right, (top+target)/height)
    badge = platform_badge(settings.platform_name, target)
    badge_width = badge.width
    badge.close()
    gap = mm_to_px(settings.platform_gap_mm, settings.dpi)
    if settings.platform_below_marker and not settings.platform_reuse_qr and settings.color_block_enabled:
        return 0, 0, badge_width, target
    # Developer mode may explicitly reuse verified QR-card space even while
    # the original header gap is preserved.
    x = (header_space(path, region, width, height, badge_width, target, gap, degrees)
         if settings.platform_reuse_qr or not (settings.preserve_header_gap and degrees % 180 == 0)
         else None)
    if x is None:
        # Never append a wide platform name to the artwork's right edge.
        x = -gap-badge_width
    return x, top, badge_width, target


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
    if not any(token in template for token in ('{完整文件名}', '{文件名}', '{filename}', '{stem}')):
        template = (template.strip()+' {完整文件名}').strip()
    return (template.strip()+' · 正序 {编号}/{总数} · 倒序 {倒序}/{总数}').strip()
