"""Final marker/text geometry checks shared by planning and rendering."""
from math import ceil, floor

from automatic_print.layout_engine.domain.models import mm_to_px


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


def validate_stack(path, p, settings):
    if (settings.cutter_mode != 'free' and p.number_width_px and p.number_height_px
            and not getattr(p, 'rotation_degrees', 0) % 180):
        from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
        band = detect_guide_band(path)
        if band is not None:
            band = band.rotated(getattr(p, 'rotation_degrees', 0))
            card_left = p.x_px+floor(band.left*p.width_px)
            card_right = p.x_px+ceil(band.right*p.width_px)
            card_top = p.y_px+round(band.top*p.height_px)
            card_bottom = p.y_px+round(band.bottom*p.height_px)
            card_on_left = (band.left+band.right)/2 < .5
            inward = (p.number_x_px >= card_right if card_on_left else
                      p.number_x_px+p.number_width_px <= card_left)
            if (inward and p.x_px <= p.number_x_px and
                    p.number_x_px+p.number_width_px <= p.x_px+p.width_px and
                    card_top <= p.number_y_px and
                    p.number_y_px+p.number_height_px <= card_bottom):
                return
            raise ValueError(f'{path.name}：标签文字未在膜标签朝图片内部一侧的安全位置，禁止输出。')
    if (settings.cutter_mode != 'free' and getattr(p, 'rotation_degrees', 0) % 180
            and p.number_width_px and p.number_height_px):
        from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
        band = detect_guide_band(path)
        if band is not None and not in_short_edge_space(
                band.rotated(p.rotation_degrees), p.width_px, p.height_px,
                (p.number_x_px-p.x_px, p.number_y_px-p.y_px,
                 p.number_width_px, p.number_height_px)):
            raise ValueError(f'{path.name}：旋转标签未在膜标签安全空白的短边，禁止输出。')
        if (band is not None and not settings.preserve_header_gap and settings.platform_below_marker
                and not settings.platform_reuse_qr
                and p.color_block_width_px and p.platform_width_px):
            platform_y = (p.color_block_y_px+p.color_block_height_px+
                          mm_to_px(settings.number_gap_mm, settings.dpi))
            if (p.platform_x_px != p.color_block_x_px
                    or p.platform_y_px != platform_y):
                raise ValueError(f'{path.name}：平台文字未在刀码正下方，禁止输出。')
        if band is not None:
            return
    if ((settings.preserve_header_gap and settings.cutter_mode != 'free')
            or not settings.platform_below_marker or not p.color_block_width_px):
        return
    if (settings.cutter_left_marker_external and settings.platform_reuse_qr
            and p.number_width_px):
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
