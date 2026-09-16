from .labels import label_badge, settings_label_badge
from .membrane_region import detect_membrane_region
from .images import print_dimensions
from .models import mm_to_px
from .measurement_timing import measured


@measured('普通标签文字测量')
def source_label_badge(text, settings, path, degrees=0):
    if settings.cutter_mode != "free":
        maximum = mm_to_px(settings.color_block_width_mm, settings.dpi)
        if settings.preserve_header_gap:
            region = detect_membrane_region(path)
            if region is None:
                raise ValueError(
                    f"{path.name}：未能可靠识别膜标签高度范围，禁止把文字放入膜标签与图案之间。"
                )
            size = print_dimensions(path, settings.dpi)
            width = mm_to_px(size.width_mm, settings.dpi)
            height = mm_to_px(size.height_mm, settings.dpi)
            if degrees % 180:
                width, height = height, width
            region = region.rotated(degrees)
            maximum = max(1, round((region.right-region.left)*width))
            available_height = max(1, round((region.bottom-region.top)*height))
            badge = label_badge(
                text, settings.dpi, settings.number_font_size_mm, maximum
            )
            if badge.height > available_height:
                badge.close()
                raise ValueError(
                    f"{path.name}：标签文字无法完整放入膜标签高度范围，禁止输出。"
                )
            return badge
        return label_badge(text, settings.dpi, settings.number_font_size_mm, maximum)
    if not settings.label_detect_region:
        return settings_label_badge(text, settings)
    region = detect_membrane_region(path)
    if region is None:
        raise ValueError(f"{path.name}：未能可靠识别独立膜标签区域，请检查原图；未使用默认高度。")
    size = print_dimensions(path, settings.dpi)
    width, height = mm_to_px(size.width_mm, settings.dpi), mm_to_px(size.height_mm, settings.dpi)
    if degrees % 180:
        width, height = height, width
    region = region.rotated(degrees)
    target_height = max(1, round((region.bottom-region.top)*height))
    target_width = max(1, round((region.right-region.left)*width))
    # Search font size using real glyph bounds and wrapped whole-text height.
    low, high, best = 2.0, target_height * 25.4 / settings.dpi * 2, None
    for _ in range(15):
        font_mm = (low+high)/2
        badge = label_badge(text, settings.dpi, font_mm, target_width)
        if badge.height <= target_height and badge.width <= target_width:
            if best is not None:
                best.close()
            best, low = badge, font_mm
        else:
            badge.close()
            high = font_mm
    if best is None:
        raise ValueError(f"{path.name}：膜标签区域不足以容纳可读文字，请缩短标签文字。")
    # Extend only transparent padding to the reference height, never distort glyphs.
    from PIL import Image
    result = Image.new("RGBA", (best.width, target_height))
    result.alpha_composite(best, (0, (target_height-best.height)//2))
    best.close()
    return result
