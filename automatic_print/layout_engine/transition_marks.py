"""Printed horizontal notices, strictly outside all image/label/marker rectangles."""
from PIL import ImageDraw

from .models import mm_to_px


def transition_rects(planned, settings, width, end_notice='批次结束'):
    if not settings.transition_lines or not planned:
        return []
    groups = {}
    for _, p in planned:
        groups.setdefault(p.cut_zone, []).append(p)
    ordered = sorted(groups.values(), key=lambda rows: min(p.row_y_px for p in rows))
    gap = mm_to_px(settings.transition_gap_mm, settings.dpi)
    thickness = max(1, mm_to_px(settings.transition_line_mm, settings.dpi))
    rects = []
    for index, rows in enumerate(ordered):
        end = max(p.y_px+p.height_px for p in rows)
        kind = end_notice if index == len(ordered)-1 else '进入旋转区 / 换刀'
        rects.append({'x': 0, 'y': end+gap, 'width': width, 'height': thickness,
                      'kind': kind})
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


def marked_height(planned, settings, width, height):
    rects = transition_rects(planned, settings, width)
    tail = mm_to_px(settings.margin_mm, settings.dpi)
    return max([height]+[r['y']+r['height']+tail for r in rects])


def paint_transition_lines(canvas, rects, use_vips=False):
    for r in rects:
        x, y, width, height = r['x'], r['y'], r['width'], r['height']
        if use_vips:
            import pyvips
            line = pyvips.Image.black(width, height, bands=4).new_from_image(
                [255, 0, 0, 255]).copy(interpretation='srgb')
            canvas = canvas.composite2(line, 'over', x=x, y=y)
        else:
            ImageDraw.Draw(canvas).rectangle((x, y, x+width-1, y+height-1), fill=(255, 0, 0, 255))
    return canvas


def rotation_marker_item(item, settings):
    from dataclasses import replace
    shift = mm_to_px(settings.rotation_marker_shift_mm, settings.dpi)
    if not shift or not item.block_width:
        return item
    block = item.block_rx+shift
    from .rotated_marks import qr_relative_item
    if qr_relative_item(item):
        from .marker_space import transparent_rect
        if item.platform_width and block < item.platform_rx+item.platform_width and block+item.block_width > item.platform_rx and item.block_ry < item.platform_ry+item.platform_height and item.block_ry+item.block_height > item.platform_ry:
            raise ValueError(f'{item.path.name}：旋转区刀码偏移会覆盖平台文字，禁止输出。')
        if block+item.block_width > item.image_rx and not transparent_rect(
            item.path, item.width, item.height, item.rotation_degrees,
            (block-item.image_rx, item.block_ry-item.image_ry, item.block_width, item.block_height)):
            raise ValueError(f'{item.path.name}：旋转区刀码偏移会覆盖原图，禁止输出。')
        return replace(item, block_rx=block)
    label = item.label_rx+shift
    if block+item.block_width > item.image_rx or (item.label_width and label+item.label_width > item.image_rx):
        from .marker_space import can_embed_marker
        if not can_embed_marker(item.path, item.width, item.height, item.rotation_degrees,
            (block-item.image_rx, item.block_ry-item.image_ry, item.block_width, item.block_height),
            (label-item.image_rx, item.label_ry-item.image_ry, item.label_width, item.label_height),
            (item.platform_rx-item.image_rx, item.platform_ry-item.image_ry, item.platform_width, item.platform_height)):
            raise ValueError(f'{item.path.name}：旋转区刀码右移后会碰到图片，请增加色块与图片间距。')
    return replace(item, block_rx=block, label_rx=label)
