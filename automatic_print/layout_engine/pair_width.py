"""Developer-only S/M/L width cap shared by preview and production."""
from dataclasses import replace

from .images import print_dimensions
from .measurement_session import resolved_name
from .models import mm_to_px
from .source_metadata import source_size


ELIGIBLE_SIZES = {'S', 'M', 'L'}


def apply_pair_width_cap(paths, settings, progress=None):
    if not (settings.force_small_pair_width
            and settings.cutter_mode == 'dual'
            and settings.cutter_majority_two_zone):
        return settings
    requested_cap = settings.force_small_pair_width_mm
    cap = min(requested_cap, _safe_artwork_width(paths, settings))
    if cap <= 0:
        raise ValueError('强制双排宽度必须大于 0 毫米。')
    overrides = dict(settings.dimension_overrides)
    notices = list(settings.width_adjustments)
    for index, path in enumerate(paths, 1):
        if source_size(path) not in ELIGIBLE_SIZES:
            continue
        dimensions = print_dimensions(path, settings.dpi)
        if dimensions.width_mm <= cap:
            continue
        if not dimensions.embedded_dpi:
            raise ValueError(f'{path.name}：缺可靠DPI，不能执行 S–L 并排宽度上限。')
        factor = cap / dimensions.width_mm
        height = dimensions.height_mm * factor
        overrides[resolved_name(path)] = (cap, height)
        text = (f'S–L 并排宽度上限：原尺寸 {dimensions.width_mm:.2f}×{dimensions.height_mm:.2f} 毫米，'
                f'等比缩小为 {cap:.2f}×{height:.2f} 毫米（{factor*100:.2f}%）；'
                f'用户上限 {requested_cap:.2f} 毫米，已扣除刀码安全占位；'
                '原文件未修改，预览和输出使用相同尺寸，刀码仍服从本区域统一刀位。')
        notices.append((path.name, text, str(path)))
        if progress:
            progress('S–L 并排宽度上限', index, len(paths), path.name+' · '+text)
    return replace(settings, dimension_overrides=tuple(overrides.items()),
                   width_adjustments=tuple(notices))


def _safe_artwork_width(paths, settings):
    lane = settings.media_width_mm / 2 - settings.cutter_safety_mm
    marker = settings.color_block_width_mm if settings.color_block_enabled else 0
    if settings.number_images and settings.platform_name and settings.platform_font_height_mm > 0:
        from .platform_label import platform_badge, platform_text
        target = max(2, mm_to_px(settings.platform_font_height_mm, settings.dpi))
        for path in paths:
            badge = platform_badge(platform_text(path, settings), target)
            marker = max(marker, badge.width * 25.4 / settings.dpi)
            badge.close()
    # The external cutter marker touches the source QR-card edge in the
    # preserved-header production layout; do not reserve the old 5 mm gap.
    reserve = marker
    return max(1, lane - reserve - .2)
