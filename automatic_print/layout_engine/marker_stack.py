"""A single left-aligned marker column: block, platform, then ordinary label."""
from .models import mm_to_px


def header_safe_coordinates(
    path, settings, image_size, degrees, block, label, platform,
):
    """Keep added text beside the cutter mark and inside the label-card height."""
    if (not settings.preserve_header_gap or settings.cutter_mode == 'free'
            or not label[2] or not label[3]):
        return block, label, platform
    from .cut_guide_geometry import detect_guide_band
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
    if lh > bottom-top:
        raise ValueError(f'{path.name}：标签文字无法完整放入膜标签高度范围，禁止输出。')
    # The cutter marker touches the source. All added text must reuse verified
    # transparent pixels inside the rotated source header band, never the lane
    # between the marker, QR card and artwork.
    block_x = -bw if bw else 0
    from .platform_space import header_space
    reserved = ()
    if pw and ph:
        if ph > bottom-top:
            raise ValueError(f'{path.name}：平台文字无法完整放入膜标签高度范围，禁止输出。')
        px = header_space(path, region, image_size[0], height, pw, ph, 0, degrees)
        if px is None:
            raise ValueError(f'{path.name}：膜标签高度带内没有平台文字的透明空位，禁止输出。')
        py = top
        reserved = ((px, py, pw, ph),)
    label_x = header_space(
        path, region, image_size[0], height, lw, lh, 0, degrees,
        reserved=reserved,
    )
    if label_x is None:
        raise ValueError(f'{path.name}：膜标签高度带内没有批次标签的透明空位，禁止输出。')
    label_y = top
    from .rotated_marks import marker_top
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
    y = p.color_block_y_px+p.color_block_height_px+mm_to_px(settings.number_gap_mm, settings.dpi)
    if p.platform_width_px and not settings.platform_reuse_qr:
        if p.platform_x_px != p.color_block_x_px or p.platform_y_px != y:
            raise ValueError(f'{path.name}：平台文字未在刀码正下方，禁止输出。')
        y += p.platform_height_px+mm_to_px(settings.platform_gap_mm, settings.dpi)
    if p.number_width_px and (p.number_x_px != p.color_block_x_px or p.number_y_px != y):
        raise ValueError(f'{path.name}：标签文字未与平台在刀码下方纵向排列，禁止输出。')
