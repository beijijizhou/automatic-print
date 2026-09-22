"""A single left-aligned marker column: block, platform, then ordinary label."""
from automatic_print.layout_engine.domain.models import mm_to_px
from .validation.stack import in_short_edge_space, validate_stack


def header_safe_coordinates(
    path, settings, image_size, degrees, block, label, platform,
):
    """Keep batch text on the card's image-facing side without extra width."""
    rotated_short_edge = degrees % 180 != 0
    if settings.cutter_mode == 'free' or not label[2] or not label[3]:
        return block, label, platform
    from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
    region = detect_guide_band(path)
    if region is None:
        # The cutter mark remains usable without a detected card.  Added text
        # has no pixel-verified safe home, so omit it instead of blocking the
        # entire batch or guessing over the artwork.
        bx, by, bw, bh = block
        if settings.cutter_left_marker_external and bw:
            bx = -bw-max(1, mm_to_px(settings.color_block_gap_mm, settings.dpi))
        block = bx, by, bw, bh
        return block, (0, 0, 0, 0), (0, 0, 0, 0)
    _width, height = image_size
    region = region.rotated(degrees)
    top, bottom = round(region.top*height), round(region.bottom*height)
    _bx, _by, bw, bh = block
    _lx, _ly, lw, lh = label
    px, py, pw, ph = platform
    if settings.platform_reuse_qr:
        # This mode merges platform text into the separate production label.
        px = py = pw = ph = 0
    if rotated_short_edge and not settings.preserve_header_gap:
        from automatic_print.layout_engine.labeling.platform.short_edge_space import short_edge_space
        reserved = ((px, py, pw, ph),) if pw and ph else ()
        position = short_edge_space(path, region, image_size[0], height,
                                    lw, lh, degrees, reserved=reserved)
        if position is None:
            label = (0, 0, 0, 0)
        else:
            label = (*position, lw, lh)
        if settings.cutter_left_marker_external and bw:
            block = (-bw-max(1, mm_to_px(settings.color_block_gap_mm, settings.dpi)),
                     _by, bw, bh)
        return block, label, platform
    if degrees % 180:
        available_height = top if (region.top+region.bottom)/2 >= .5 else height-bottom
    else:
        available_height = bottom-top
    if lh > available_height:
        lw = lh = 0
    # A left card uses its right side; a right card uses its left side. Both
    # positions stay inside the original image footprint.
    block_x = _bx if not settings.preserve_header_gap else (-bw if bw else 0)
    from automatic_print.layout_engine.labeling.platform.platform_space import header_space
    from automatic_print.layout_engine.labeling.platform.short_edge_space import short_edge_space
    reserved = ()
    if pw and ph:
        if not settings.preserve_header_gap and not rotated_short_edge:
            reserved = ((px, py, pw, ph),)
        elif ph > available_height:
            px = py = pw = ph = 0
        if not settings.preserve_header_gap and not rotated_short_edge:
            pass  # Preserve the explicit external platform stack, if configured.
        elif degrees % 180:
            position = short_edge_space(path, region, image_size[0], height,
                                        pw, ph, degrees)
            if position is None:
                px = py = pw = ph = 0
            else:
                px, py = position
        else:
            px = header_space(path, region, image_size[0], height, pw, ph, 0, degrees)
            if px is None:
                px = py = pw = ph = 0
            else:
                py = top
        reserved = ((px, py, pw, ph),) if pw and ph else ()
    if not lw or not lh:
        label_x = label_y = 0
    elif degrees % 180:
        position = short_edge_space(path, region, image_size[0], height,
                                    lw, lh, degrees, reserved=reserved)
        if position is None:
            label_x = label_y = lw = lh = 0
        else:
            label_x, label_y = position
    else:
        label_x = header_space(
            path, region, image_size[0], height, lw, lh, 0, degrees,
            reserved=reserved, inward_from_card=True,
        )
        if label_x is None:
            label_x = label_y = lw = lh = 0
        else:
            label_y = top
    from automatic_print.layout_engine.cutting.geometry.rotated_marks import marker_top
    block_y = marker_top(region, height) if bh else 0
    return (
        (block_x, block_y, bw, bh),
        (label_x, label_y, lw, lh),
        (px, py, pw, ph),
    )


def stacked_coordinates(settings, block, label, platform):
    bx, by, bw, bh = block
    lx, ly, lw, lh = label
    px, py, pw, ph = platform
    if settings.platform_reuse_qr:
        px = py = pw = ph = 0
    if ((settings.preserve_header_gap and settings.cutter_mode != 'free')
            or not settings.platform_below_marker or not bw):
        return bx, by, lx, ly, px, py
    gap = max(1, mm_to_px(settings.color_block_gap_mm, settings.dpi))
    x = -max(bw, lw, pw)-gap
    y = by+bh+mm_to_px(settings.number_gap_mm, settings.dpi)
    label_y = y+ph+mm_to_px(settings.platform_gap_mm, settings.dpi) if ph else y
    return x, by, x, label_y, x, y
