"""Build a complete copyable report payload without rendering an output file."""
from dataclasses import asdict

from .metrics import saving_metrics


def build_preview_result(
    output_name, planned, quality, sizes, settings, analysis, gap_records,
    cut_check, order_check, width, height, baseline_height,
):
    result = {
        'preview_only': True,
        'filename': output_name,
        'dual_quality': quality,
        'size_range': sizes,
        'output_dpi': settings.dpi,
        'output_dpi_origin': settings.output_dpi_origin,
        'film_width_mm': settings.media_width_mm + settings.riin_left_mm + settings.riin_right_mm,
        'header_gap': gap_records,
        'cutter_mode': settings.cutter_mode,
        'cut_corridor': cut_check,
        'cutter_knife_mm': (
            settings.cutter_knife_mm if settings.cutter_mode == 'dual' else None
        ),
        'cutter_safety_mm': settings.cutter_safety_mm,
        'width_px': width,
        'height_px': height,
        'width_mm': round(width * 25.4 / settings.dpi, 1),
        'height_mm': round(height * 25.4 / settings.dpi, 1),
        'maximum_width_mm': settings.media_width_mm,
        'order_check': order_check,
        'analysis': analysis,
        'placements': [asdict(item) for _, item in planned],
        'rotation_count': sum(bool(item.rotation_degrees) for _, item in planned),
    }
    result.update(saving_metrics(baseline_height, height, settings.dpi))
    return result
