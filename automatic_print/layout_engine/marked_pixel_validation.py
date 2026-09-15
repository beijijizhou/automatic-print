"""Bounded-width checks: only the exact printed circles and notice rectangles pass."""
from PIL import Image, ImageChops, ImageDraw
from contextlib import ExitStack


def footer_glyphs(rectangles, left, top, right, bottom, stack):
    from .batch_footer import footer_sprite
    glyphs = {}
    for r in rectangles:
        if 'text' not in r:
            continue
        x0, y0 = max(left, r['x']), max(top, r['y'])
        x1, y1 = min(right, r['x']+r['width']), min(bottom, r['y']+r['height'])
        if x1 <= x0 or y1 <= y0:
            continue
        with footer_sprite(r) as sprite:
            with sprite.crop((x0-r['x'], y0-r['y'], x1-r['x'], y1-r['y'])) as strip:
                with strip.getchannel('A') as alpha:
                    glyph = stack.enter_context(alpha.point(lambda v: 255 if v else 0))
        glyphs[id(r)] = x0, y0, glyph
    return glyphs


def validate_marked_pillow(canvas, check, boxes=(), rectangles=(), progress=None):
    with ExitStack() as stack:
        _validate(canvas, check, boxes, rectangles, progress, stack)


def _validate(canvas, check, boxes, rectangles, progress, stack):
    if check is None:
        return
    from .cut_validation import corridor_checks
    for zone in corridor_checks(check):
        left, right = zone['safe_left_px'], zone['safe_right_px']
        top, bottom = zone.get('start_y_px', 0), zone.get('end_y_px', canvas.height)
        glyphs = footer_glyphs(rectangles, left, top, right, bottom, stack)
        for x in range(left, right, 8):
            end = min(x+8, right)
            stripe = canvas.crop((x, top, end, bottom))
            alpha = stripe.getchannel('A')
            stripe.close()
            mask = Image.new('L', (end-x, bottom-top))
            draw = ImageDraw.Draw(mask)
            for bx, by, diameter in boxes:
                if bx < end and bx+diameter > x and by < bottom and by+diameter > top:
                    if diameter == 1:
                        draw.point((bx-x, by-top), fill=255)
                    else:
                        draw.ellipse((bx-x, by-top, bx-x+diameter-1, by-top+diameter-1), fill=255)
            for r in rectangles:
                if r['x'] < end and r['x']+r['width'] > x and r['y'] < bottom and r['y']+r['height'] > top:
                    if 'text' in r:
                        gx, gy, glyph = glyphs[id(r)]
                        x0, x1 = max(x, gx), min(end, gx+glyph.width)
                        with glyph.crop((x0-gx, 0, x1-gx, glyph.height)) as cropped:
                            mask.paste(cropped, (x0-x, gy-top))
                        continue
                    draw.rectangle((r['x']-x, r['y']-top, r['x']+r['width']-x-1,
                                    r['y']+r['height']-top-1), fill=255)
            extra = ImageChops.subtract(alpha, mask)
            invalid = extra.getbbox() is not None
            alpha.close()
            mask.close()
            extra.close()
            if invalid:
                raise ValueError('标记合成后出现未经允许的切割通道像素，禁止输出。')
            if progress:
                progress('核对标记通道', end-left, right-left, '仅允许精确提示线与批次信息字形范围')
