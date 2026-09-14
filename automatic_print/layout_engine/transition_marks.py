"""Printed horizontal notices, strictly outside all image/label/marker rectangles."""
from PIL import ImageDraw

from .models import mm_to_px


def transition_rects(planned, settings, width, end_notice='批次结束'):
    if not planned or not (settings.transition_lines or settings.batch_footer_enabled):
        return []
    gap = mm_to_px(settings.transition_gap_mm, settings.dpi)
    thickness = max(1, mm_to_px(settings.transition_line_mm, settings.dpi))
    end = max(max(p.y_px+p.height_px,
                  p.number_y_px+p.number_height_px if p.number_width_px else 0,
                  p.platform_y_px+p.platform_height_px if p.platform_width_px else 0,
                  p.color_block_y_px+p.color_block_height_px if p.color_block_width_px else 0)
              for _, p in planned)
    rects = []
    if settings.batch_footer_enabled:
        from .batch_footer import footer_rect
        footer = footer_rect(planned, settings, width, end+gap, end_notice)
        rects.append(footer)
        end = footer['y']+footer['height']
    if settings.transition_lines:
        rects.append({'x': 0, 'y': end+gap, 'width': width, 'height': thickness,
                      'kind': end_notice})
    for r in rects:
        for path, p in planned:
            for name, y, w, h in (
                ('图片', p.y_px, p.width_px, p.height_px),
                ('标签', p.number_y_px, p.number_width_px, p.number_height_px),
                ('平台名称', p.platform_y_px, p.platform_width_px, p.platform_height_px),
                ('色块', p.color_block_y_px, p.color_block_width_px, p.color_block_height_px),
            ):
                if w and h and y < r['y']+r['height'] and y+h > r['y']:
                    raise ValueError(f'{path.name}：红色横向提示线与{name}重叠，请增加区域间距或调整标签。')
    return rects


def marked_height(planned, settings, width, height, end_notice='批次结束'):
    rects = transition_rects(planned, settings, width, end_notice)
    tail = mm_to_px(settings.margin_mm, settings.dpi)
    return max([height]+[r['y']+r['height']+tail for r in rects])


def paint_transition_lines(canvas, rects, use_vips=False):
    for r in rects:
        x, y, width, height = r['x'], r['y'], r['width'], r['height']
        if 'text' in r:
            from .batch_footer import footer_sprite
            sprite = footer_sprite(r)
            try:
                if use_vips:
                    import pyvips
                    badge = pyvips.Image.new_from_memory(sprite.tobytes(), width, height, 4, 'uchar').copy(interpretation='srgb')
                    canvas = canvas.composite2(badge, 'over', x=x, y=y)
                else:
                    canvas.alpha_composite(sprite, (x, y))
            finally:
                sprite.close()
            continue
        if use_vips:
            import pyvips
            line = pyvips.Image.black(width, height, bands=4).new_from_image(
                [255, 0, 0, 255]).copy(interpretation='srgb')
            canvas = canvas.composite2(line, 'over', x=x, y=y)
        else:
            ImageDraw.Draw(canvas).rectangle((x, y, x+width-1, y+height-1), fill=(255, 0, 0, 255))
    return canvas


def rotation_marker_item(item, settings):
    # Retain the caller contract; the old deliberate sensor offset is suspended.
    from .left_marker import external_left_item
    return external_left_item(item)
