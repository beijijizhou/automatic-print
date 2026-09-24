"""Shared virtual width cap for selected sizes and strict fixed-knife batches."""
from dataclasses import replace
from pathlib import Path

from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.measurement.measurement_session import resolved_name
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.intake.metadata.source_metadata import source_size
from automatic_print.layout_engine.orders.order_groups import pair_identity


PAIR_WIDTH_TITLES = ('所选尺码并排宽度上限：', '共刀并排等比缩小：')


def apply_pair_width_cap(paths, settings, progress=None):
    fixed = settings.strict_fixed_knife
    if not (settings.force_small_pair_width and settings.cutter_mode == 'dual'
            and (settings.cutter_majority_two_zone
                 or settings.counting_accuracy_layout or fixed)):
        return settings
    requested_cap = settings.force_small_pair_width_mm
    source_limit = settings.force_small_pair_source_limit_mm
    eligible_sizes = set(settings.force_small_pair_sizes)
    cap = min(requested_cap, _safe_artwork_width(paths, settings))
    if cap <= 0:
        raise ValueError('强制双排宽度必须大于 0 毫米。')
    overrides = dict(settings.dimension_overrides)
    notices = list(settings.width_adjustments)
    dimensions_by_path = {}
    factors = {}
    manual_rotations = {
        resolved_name(Path(name))
        for name, degrees in settings.manual_rotations if degrees % 360
    }
    for path in paths:
        if resolved_name(path) in manual_rotations:
            continue
        if source_size(path) not in eligible_sizes:
            continue
        dimensions = print_dimensions(path, settings.dpi)
        dimensions_by_path[path] = dimensions
        if dimensions.width_mm > source_limit:
            continue
        if dimensions.width_mm <= cap:
            continue
        if not dimensions.embedded_dpi:
            raise ValueError(f'{path.name}：缺可靠DPI，不能执行并排等比缩小。')
        factors[path] = cap / dimensions.width_mm
    if fixed:
        paired = {}
        for path in paths:
            identity = pair_identity(path)
            if identity:
                paired.setdefault(identity[0], []).append(path)
        for mates in paired.values():
            if any(source_size(path) not in eligible_sizes or
                   dimensions_by_path[path].width_mm > source_limit
                   for path in mates):
                for path in mates:
                    factors.pop(path, None)
                continue
            factor = min(factors.get(path, 1.0) for path in mates)
            if factor < 1.0:
                for path in mates:
                    factors[path] = factor
    for index, path in enumerate(paths, 1):
        if path not in factors:
            continue
        dimensions = dimensions_by_path[path]
        if not dimensions.embedded_dpi:
            raise ValueError(f'{path.name}：双面同倍率缩小缺可靠DPI。')
        factor = factors[path]
        width = dimensions.width_mm * factor
        height = dimensions.height_mm * factor
        overrides[resolved_name(path)] = (width, height)
        title = '共刀并排等比缩小' if fixed else '所选尺码并排宽度上限'
        text = (f'{title}：原尺寸 {dimensions.width_mm:.2f}×{dimensions.height_mm:.2f} 毫米，'
                f'等比缩小为 {width:.2f}×{height:.2f} 毫米（{factor*100:.2f}%）；'
                f'原宽上限 {source_limit:.2f} 毫米，目标上限 {requested_cap:.2f} 毫米，'
                '已扣除刀码安全占位；'
                '原文件未修改，预览和输出使用相同尺寸，刀码仍服从本区域统一刀位。')
        notices.append((path.name, text, str(path)))
        if progress:
            progress(title, index, len(paths), path.name+' · '+text)
    return replace(settings, dimension_overrides=tuple(overrides.items()),
                   width_adjustments=tuple(notices))


def without_pair_width_scaling(settings):
    """Return original dimensions for rotation candidates only."""
    scaled = {
        resolved_name(Path(source_path))
        for _name, text, source_path in settings.width_adjustments
        if text.startswith(PAIR_WIDTH_TITLES)
    }
    if not scaled:
        return settings
    return replace(
        settings,
        dimension_overrides=tuple(
            (name, dimensions)
            for name, dimensions in settings.dimension_overrides
            if name not in scaled
        ),
        width_adjustments=tuple(
            adjustment
            for adjustment in settings.width_adjustments
            if not adjustment[1].startswith(PAIR_WIDTH_TITLES)
        ),
    )


def remove_rotated_pair_width_adjustments(settings, planned):
    """Do not report a pair-width reduction for final rotated placements."""
    rotated = {
        resolved_name(path)
        for path, placement in planned
        if placement.rotation_degrees % 360
    }
    if not rotated:
        return settings
    rejected = {
        resolved_name(Path(source_path))
        for _name, text, source_path in settings.width_adjustments
        if text.startswith(PAIR_WIDTH_TITLES)
        and resolved_name(Path(source_path)) in rotated
    }
    if not rejected:
        return settings
    return replace(
        settings,
        dimension_overrides=tuple(
            (name, dimensions)
            for name, dimensions in settings.dimension_overrides
            if name not in rejected
        ),
        width_adjustments=tuple(
            adjustment
            for adjustment in settings.width_adjustments
            if not (
                adjustment[1].startswith(PAIR_WIDTH_TITLES)
                and resolved_name(Path(adjustment[2])) in rejected
            )
        ),
    )


def _safe_artwork_width(paths, settings):
    lane = (min(settings.cutter_knife_mm,
                settings.media_width_mm - settings.cutter_knife_mm)
            if settings.strict_fixed_knife else settings.media_width_mm / 2)
    lane -= settings.cutter_safety_mm
    marker = settings.color_block_width_mm if settings.color_block_enabled else 0
    if settings.number_images and settings.platform_name and settings.platform_font_height_mm > 0:
        from automatic_print.layout_engine.labeling.platform.platform_label import platform_badge, platform_text
        target = max(2, mm_to_px(settings.platform_font_height_mm, settings.dpi))
        for path in paths:
            badge = platform_badge(platform_text(path, settings), target)
            marker = max(marker, badge.width * 25.4 / settings.dpi)
            badge.close()
    # The external cutter marker touches the source QR-card edge in the
    # preserved-header production layout; do not reserve the old 5 mm gap.
    reserve = marker
    return max(1, lane - reserve - .2)
