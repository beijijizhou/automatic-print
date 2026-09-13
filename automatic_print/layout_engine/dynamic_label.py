from .labels import label_badge, settings_label_badge
from .membrane_region import detect_membrane_region
from .images import print_dimensions
from .models import mm_to_px


def source_label_badge(text, settings, path, degrees=0):
    if settings.cutter_mode != "free":
        return label_badge(text, settings.dpi, settings.number_font_size_mm,
                           mm_to_px(settings.color_block_width_mm, settings.dpi))
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
