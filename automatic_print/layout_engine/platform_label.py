"""A separate readable platform badge, sized from the actual rotated QR."""
from PIL import Image, ImageDraw, ImageFont
from functools import lru_cache

from .cut_guide_geometry import detect_guide_band
from .models import mm_to_px


def _font(size):
    for path in ('C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/simhei.ttf',
                 '/System/Library/Fonts/Supplemental/Songti.ttc',
                 '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    raise ValueError('未找到中文字体，无法清晰打印平台名称。请安装微软雅黑或思源黑体。')


def platform_badge(text, target_height):
    width, pixels = _badge_data(text, target_height)
    return Image.frombytes('RGBA', (width, target_height), pixels)


@lru_cache(maxsize=64)
def _badge_data(text, target_height):
    # Cache immutable pixels, never share a font face or mutable image across workers.
    if target_height < 2:
        raise ValueError('二维码打印高度太小，无法显示可读的平台名称。')
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
        raise ValueError('二维码高度不足以容纳平台名称。')
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
    region = detect_guide_band(path)
    if region is None:
        raise ValueError(f'{path.name}：未识别到二维码，无法确定平台文字高度；请检查图片或关闭平台标记。')
    region = region.rotated(degrees)
    top = round(region.top*height)
    target = max(1, round(region.bottom*height)-top)
    badge = platform_badge(settings.platform_name, target)
    badge_width = badge.width
    badge.close()
    gap = mm_to_px(settings.platform_gap_mm, settings.dpi)
    x = -gap-badge_width if (region.left+region.right)/2 < .5 else width+gap
    return x, top, badge_width, target


def numbered_template(settings):
    template = settings.label_text_template
    if settings.label_machine_enabled and not any(token in template for token in ('{机器号}', '{machine}')):
        template = (template.strip()+' {机器号}').strip()
    if settings.label_sequence_enabled and not any(token in template for token in ('{编号}', '{number}')):
        template = (template.strip()+' {编号}').strip()
    return template
