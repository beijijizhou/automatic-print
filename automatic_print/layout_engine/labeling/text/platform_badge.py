"""Immutable pixel data for bounded platform-name badges."""
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont


@lru_cache(maxsize=128)
def _font(size):
    for path in (
        'C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/simhei.ttf',
        '/System/Library/Fonts/Supplemental/Songti.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    raise ValueError('未找到中文字体，无法清晰打印平台名称。请安装微软雅黑或思源黑体。')


@lru_cache(maxsize=2048)
def badge_data(text, target_height):
    """Cache immutable pixels, never a mutable image or shared font face."""
    if target_height < 2:
        raise ValueError('膜标签打印高度太小，无法显示可读的平台名称。')
    measure = ImageDraw.Draw(Image.new('L', (1, 1)))
    low, high, best = 1, target_height * 3, None
    while low <= high:
        size = (low + high) // 2
        font = _font(size)
        box = measure.textbbox((0, 0), text, font=font, stroke_width=1)
        if box[3] - box[1] <= target_height:
            best = font, box
            low = size + 1
        else:
            high = size - 1
    if best is None:
        raise ValueError('膜标签高度不足以容纳平台名称。')
    font, box = best
    badge = Image.new('RGBA', (box[2] - box[0], target_height))
    ImageDraw.Draw(badge).text(
        (-box[0], (target_height - (box[3] - box[1])) // 2 - box[1]),
        text, font=font, fill='black', stroke_width=1,
    )
    try:
        return badge.width, badge.tobytes()
    finally:
        badge.close()
