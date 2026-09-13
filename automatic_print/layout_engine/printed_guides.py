"""Physical-size QR-band knife dots, shared by preview and lossless output."""
from PIL import Image, ImageDraw

from .cut_guide_geometry import detect_guide_band, guide_spans
from .models import mm_to_px


def dot_boxes(spans, dpi):
    diameter = max(1, mm_to_px(.6, dpi))
    step = max(diameter + 1, mm_to_px(1.4, dpi))
    for span in spans:
        for top in range(span.top, span.bottom - diameter + 1, step):
            yield (span.knife_x - diameter // 2, top, diameter)


def collect_guides(planned, settings, progress=None):
    if settings.cutter_mode != 'dual':
        return [], []
    paths = list(dict.fromkeys(path for path, _ in planned))
    bands = {}
    for index, path in enumerate(paths, 1):
        bands[path] = detect_guide_band(path)
        if progress:
            progress('识别输出辅助线', index, len(paths), path.name)
    return guide_spans(planned, settings, bands), [p.name for p in paths if bands[p] is None]


def dot_sprite(diameter):
    sprite = Image.new('RGBA', (diameter, diameter))
    if diameter == 1:
        sprite.putpixel((0, 0), (255, 0, 0, 255))
    else:
        ImageDraw.Draw(sprite).ellipse((0, 0, diameter-1, diameter-1), fill=(255, 0, 0, 255))
    return sprite


def paint_guides(canvas, boxes, use_vips=False):
    if not boxes:
        return canvas
    sprite = dot_sprite(boxes[0][2])
    try:
        if not use_vips:
            for x, y, _ in boxes:
                canvas.alpha_composite(sprite, (x, y))
            return canvas
        import pyvips
        dot = pyvips.Image.new_from_memory(sprite.tobytes(), sprite.width, sprite.height,
                                         4, 'uchar').copy(interpretation='srgb')
        return canvas.composite([dot]*len(boxes), ['over']*len(boxes),
                                x=[b[0] for b in boxes], y=[b[1] for b in boxes])
    finally:
        sprite.close()


def vips_corridor_is_clear(image, check, boxes=()):
    """Allow exactly our circle alpha mask, never a whole band or arbitrary red ink."""
    import pyvips
    left, right = check['safe_left_px'], check['safe_right_px']
    top, bottom = check.get('start_y_px', 0), check.get('end_y_px', image.height)
    alpha = image.crop(left, top, right-left, bottom-top)[3]
    mask = pyvips.Image.black(right-left, bottom-top)
    for x, y, diameter in boxes:
        if x >= right or x+diameter <= left or y >= bottom or y+diameter <= top:
            continue
        sprite = dot_sprite(diameter)
        try:
            dot = pyvips.Image.new_from_memory(sprite.getchannel('A').tobytes(),
                                               diameter, diameter, 1, 'uchar')
            x0, y0 = max(left, x), max(top, y)
            x1, y1 = min(right, x+diameter), min(bottom, y+diameter)
            mask = mask.insert(dot.crop(x0-x, y0-y, x1-x0, y1-y0), x0-left, y0-top)
        finally:
            sprite.close()
    return (alpha > mask).max() == 0


def validate_vips_canvas(canvas, check):
    if check is None:
        return
    for zone in check.get('zones', [check]):
        if not vips_corridor_is_clear(canvas, zone):
            raise ValueError('合成图片进入整批切割安全通道，已禁止保存打印文件。')
