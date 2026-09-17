"""Apply platform label gaps while rendering, without intermediate PNG copies."""
from pathlib import Path

from PIL import Image


def enabled(settings):
    return settings.platform_name.strip().casefold() in {'haloo', '隆丰'}


def gap_map(settings):
    return {row[0]: row[1:] for row in getattr(settings, 'header_gap_overrides', ())}


def entry(path, settings):
    return gap_map(settings).get(str(Path(path).resolve()))


def expand_vips(source, path, settings, pyvips):
    values = entry(path, settings)
    if not values:
        return source
    split, added, _mtime_ns, _size = values
    top = source.crop(0, 0, source.width, split)
    body = source.crop(0, split, source.width, source.height - split)
    blank = pyvips.Image.black(source.width, added, bands=source.bands).cast(source.format)
    return top.join(blank, 'vertical').join(body, 'vertical')


def expand_pillow(source, path, settings):
    values = entry(path, settings)
    if not values:
        return source
    split, added, _mtime_ns, _size = values
    canvas = Image.new('RGBA', (source.width, source.height + added))
    canvas.paste(source.crop((0, 0, source.width, split)), (0, 0))
    canvas.paste(source.crop((0, split, source.width, source.height)), (0, split + added))
    source.close()
    return canvas
