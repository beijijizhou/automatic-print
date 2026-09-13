"""Bounded-width checks: only the exact printed circles and notice rectangles pass."""
from PIL import Image, ImageChops, ImageDraw


def validate_marked_pillow(canvas, check, boxes=(), rectangles=(), progress=None):
    if check is None:
        return
    for zone in check.get('zones', [check]):
        left, right = zone['safe_left_px'], zone['safe_right_px']
        top, bottom = zone.get('start_y_px', 0), zone.get('end_y_px', canvas.height)
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
                progress('核对标记通道', end-left, right-left, '仅允许精确红色点线和横向提示线范围')
