"""A single left-aligned marker column: block, platform, then ordinary label."""
from math import ceil, floor
from automatic_print.layout_engine.domain.models import mm_to_px


def header_safe_coordinates(
    path, settings, image_size, degrees, block, label, platform,
):
    """Use verified space between the left cutter mark and source label card."""
    if (not settings.preserve_header_gap or settings.cutter_mode == 'free'
            or not label[2] or not label[3]):
        return block, label, platform
    from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
    region = detect_guide_band(path)
    if region is None:
        raise ValueError(
            f'{path.name}：未能可靠识别膜标签高度范围，禁止把文字放入膜标签与图案之间。'
        )
    _width, height = image_size
    region = region.rotated(degrees)
    top, bottom = round(region.top*height), round(region.bottom*height)
    _bx, _by, bw, bh = block
    _lx, _ly, lw, lh = label
    px, py, pw, ph = platform
    if degrees % 180:
        available_height = top if (region.top+region.bottom)/2 >= .5 else height-bottom
    else:
        available_height = bottom-top
    if lh > available_height:
        raise ValueError(f'{path.name}：标签文字无法完整放入膜标签高度范围，禁止输出。')
    # First use source-header transparency before the card. A missing rectangle
    # triggers the shared, full-batch external-gutter fallback.
    block_x = -bw if bw else 0
    from automatic_print.layout_engine.labeling.platform.platform_space import (
        card_rect_clear, header_space,
    )
    from automatic_print.layout_engine.labeling.platform.short_edge_space import short_edge_space
    reserved = ()
    if pw and ph:
        if ph > available_height and not settings.platform_reuse_qr:
            raise ValueError(f'{path.name}：平台文字无法完整放入膜标签高度范围，禁止输出。')
        if settings.platform_reuse_qr:
            if not card_rect_clear(path, image_size[0], height, degrees,
                                   (px, py, pw, ph)):
                # A platform badge is optional. Keep the source image and the
                # cutter geometry unchanged when the QR card has no verified
                # blank rectangle.
                px = py = pw = ph = 0
        elif degrees % 180:
            position = short_edge_space(path, region, image_size[0], height,
                                        pw, ph, degrees)
            if position is None:
                raise ValueError(f'{path.name}：膜标签短边没有平台文字的透明空位，禁止输出。')
            px, py = position
        else:
            px = header_space(path, region, image_size[0], height, pw, ph, 0, degrees)
            if px is None:
                raise ValueError(f'{path.name}：膜标签高度带内没有平台文字的透明空位，禁止输出。')
            py = top
        reserved = ((px, py, pw, ph),) if pw and ph else ()
    if degrees % 180:
        position = short_edge_space(path, region, image_size[0], height,
                                    lw, lh, degrees, reserved=reserved)
        if position is None:
            raise ValueError(f'{path.name}：膜标签短边没有批次标签的透明空位，禁止输出。')
        label_x, label_y = position
    else:
        label_x = header_space(
            path, region, image_size[0], height, lw, lh, 0, degrees,
            reserved=reserved, between_marker_and_card=True,
        )
        if label_x is None:
            raise ValueError(f'{path.name}：膜标签高度带内没有批次标签的透明空位，禁止输出。')
        label_y = top
    from automatic_print.layout_engine.cutting.geometry.rotated_marks import marker_top
    block_y = marker_top(region, height) if bh else 0
    return (
        (block_x, block_y, bw, bh),
        (label_x, label_y, lw, lh),
        (px, py, pw, ph),
    )


def in_short_edge_space(region, width, height, rect):
    """Require the whole badge to remain inside the image beside a short end."""
    x, y, w, h = rect
    left, right = ceil(region.left*width), floor(region.right*width)
    if not (0 <= x and x+w <= width and left <= x and x+w <= right
            and 0 <= y and y+h <= height):
        return False
    if (region.top+region.bottom)/2 >= .5:
        return y+h <= floor(region.top*height)
    return y >= ceil(region.bottom*height)


def stacked_coordinates(settings, block, label, platform):
    bx, by, bw, bh = block
    lx, ly, lw, lh = label
    px, py, pw, ph = platform
    if ((settings.preserve_header_gap and settings.cutter_mode != 'free')
            or not settings.platform_below_marker or not bw):
        return bx, by, lx, ly, px, py
    gap = max(1, mm_to_px(settings.color_block_gap_mm, settings.dpi))
    # A badge reused inside the source QR card is not part of the external
    # cutter-marker column. Reserving its width here would count it twice and
    # can incorrectly make otherwise safe multi-column rows impossible.
    external_platform_width = 0 if settings.platform_reuse_qr else pw
    x = -max(bw, lw, external_platform_width)-gap
    y = by+bh+mm_to_px(settings.number_gap_mm, settings.dpi)
    external_platform = ph and not settings.platform_reuse_qr
    label_y = y+ph+mm_to_px(settings.platform_gap_mm, settings.dpi) if external_platform else y
    return x, by, x, label_y, (px if settings.platform_reuse_qr else x), (py if settings.platform_reuse_qr else y)


def validate_stack(path, p, settings):
    if ((settings.preserve_header_gap and settings.cutter_mode != 'free')
            or not settings.platform_below_marker or not p.color_block_width_px):
        return
    if (settings.cutter_left_marker_external and settings.platform_reuse_qr
            and p.number_width_px):
        # The external corridor has two verified arrangements: a horizontal
        # label inside the original header band, or a vertical label below the
        # cutter mark, entirely outside the source image. Neither geometry
        # may intrude into the artwork.
        gap = mm_to_px(settings.number_gap_mm, settings.dpi)
        outside = (p.color_block_x_px+p.color_block_width_px <= p.x_px
                   and p.number_x_px+p.number_width_px <= p.x_px)
        vertical = (p.number_x_px == p.color_block_x_px
                    and p.number_y_px == p.color_block_y_px+p.color_block_height_px+gap)
        horizontal = p.number_x_px >= p.color_block_x_px+p.color_block_width_px
        if horizontal and outside:
            from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
            band = detect_guide_band(path)
            if band is not None:
                band = band.rotated(p.rotation_degrees)
                top = p.y_px+round(band.top*p.height_px)
                bottom = p.y_px+round(band.bottom*p.height_px)
                horizontal = top <= p.number_y_px and p.number_y_px+p.number_height_px <= bottom
            else:
                horizontal = False
        if not outside or not (vertical or horizontal):
            raise ValueError(
                f'{path.name}：标签文字未位于刀码与膜标签之间的安全空白，禁止输出。'
                f'刀码=({p.color_block_x_px},{p.color_block_y_px},'
                f'{p.color_block_width_px},{p.color_block_height_px})；'
                f'标签=({p.number_x_px},{p.number_y_px},'
                f'{p.number_width_px},{p.number_height_px})；原图左边界={p.x_px}。'
            )
        return
    y = p.color_block_y_px+p.color_block_height_px+mm_to_px(settings.number_gap_mm, settings.dpi)
    if p.platform_width_px and not settings.platform_reuse_qr:
        if p.platform_x_px != p.color_block_x_px or p.platform_y_px != y:
            raise ValueError(f'{path.name}：平台文字未在刀码正下方，禁止输出。')
        y += p.platform_height_px+mm_to_px(settings.platform_gap_mm, settings.dpi)
    if p.number_width_px and (p.number_x_px != p.color_block_x_px or p.number_y_px != y):
        raise ValueError(f'{path.name}：标签文字未与平台在刀码下方纵向排列，禁止输出。')
