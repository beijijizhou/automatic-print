"""Thread-local bounded font cache for production labels."""
from collections import OrderedDict
from threading import local

from PIL import ImageFont


_FONTS = local()


def cached_bold_font(size: int):
    if not hasattr(_FONTS, 'cache'):
        _FONTS.cache = OrderedDict()
    cache = _FONTS.cache
    if size not in cache:
        cache[size] = _load_font(size)
        if len(cache) > 32:
            cache.popitem(last=False)
    cache.move_to_end(size)
    return cache[size]


def _load_font(size: int):
    candidates = (
        'DejaVuSans-Bold.ttf', 'arialbd.ttf',
        'C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/Arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()
