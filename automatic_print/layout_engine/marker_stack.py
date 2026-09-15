"""A single left-aligned marker column: block, platform, then ordinary label."""
from .models import mm_to_px


def stacked_coordinates(settings, block, label, platform):
    bx, by, bw, bh = block
    lx, ly, lw, lh = label
    px, py, pw, ph = platform
    if not settings.platform_below_marker or not bw:
        return bx, by, lx, ly, px, py
    gap = max(1, mm_to_px(settings.color_block_gap_mm, settings.dpi))
    x = -max(bw, lw, pw)-gap
    y = by+bh+mm_to_px(settings.number_gap_mm, settings.dpi)
    external_platform = ph and not settings.platform_reuse_qr
    label_y = y+ph+mm_to_px(settings.platform_gap_mm, settings.dpi) if external_platform else y
    return x, by, x, label_y, (px if settings.platform_reuse_qr else x), (py if settings.platform_reuse_qr else y)


def validate_stack(path, p, settings):
    if not settings.platform_below_marker or not p.color_block_width_px:
        return
    y = p.color_block_y_px+p.color_block_height_px+mm_to_px(settings.number_gap_mm, settings.dpi)
    if p.platform_width_px and not settings.platform_reuse_qr:
        if p.platform_x_px != p.color_block_x_px or p.platform_y_px != y:
            raise ValueError(f'{path.name}：平台文字未在刀码正下方，禁止输出。')
        y += p.platform_height_px+mm_to_px(settings.platform_gap_mm, settings.dpi)
    if p.number_width_px and (p.number_x_px != p.color_block_x_px or p.number_y_px != y):
        raise ValueError(f'{path.name}：标签文字未与平台在刀码下方纵向排列，禁止输出。')
