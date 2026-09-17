"""Build the stable production result payload after rendering completes."""
from dataclasses import asdict

from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.cutting.geometry.knife_positions import result_fields
from automatic_print.layout_engine.labeling.base.labels import normalize_machine_number
from automatic_print.layout_engine.reporting.metrics import saving_metrics


def build_result(*, filename, output_path, settings, paths, planned, analysis,
                 quality, sizes, gap_records, cut_check, order_check,
                 guide_spans, guide_boxes, missing_guides, transitions, width, height,
                 baseline_height, output_format, use_vips, save_details,
                 reading_seconds, combining_seconds, saving_seconds,
                 validation_seconds, total_seconds):
    size = output_path.stat().st_size
    result = {
        'filename': filename, 'dual_quality': quality,
        'size_range': sizes, 'output_dpi': settings.dpi,
        'film_width_mm': settings.media_width_mm + settings.riin_left_mm + settings.riin_right_mm,
        'output_dpi_origin': settings.output_dpi_origin,
        'transition_marks': transitions, 'rotation_marker_shift_mm': 0,
        'machine_number': normalize_machine_number(settings.machine_number),
        'header_gap': gap_records, 'cutter_mode': settings.cutter_mode,
        'platform_name': settings.platform_name,
        'platform_font_height_mm': settings.platform_font_height_mm,
        'label_sequence_enabled': settings.label_sequence_enabled,
        'cut_corridor': cut_check,
        'printed_guides': {
            'span_count': len(guide_spans), 'dot_count': len(guide_boxes),
            'missing_qr': missing_guides,
        },
        **result_fields(planned, settings),
        'cutter_safety_mm': settings.cutter_safety_mm,
        'source_dimensions': [
            {'source': path.name, **asdict(print_dimensions(path, settings.dpi))}
            for path in paths
        ],
        'width_px': width, 'height_px': height,
        'width_mm': round(width * 25.4 / settings.dpi, 1),
        'maximum_width_mm': settings.media_width_mm,
        'trimmed_right_mm': round(max(0, settings.media_width_mm-width*25.4/settings.dpi), 1),
        'height_mm': round(height * 25.4 / settings.dpi, 1),
        'file_size_bytes': size,
        'output_format': 'TIFF' if output_format == 'tiff' else 'PNG',
        'pixel_format': 'RGBA', 'bits_per_channel': 8, 'alpha_channel': True,
        'png_compression_level': settings.png_compression_level,
        'worker_threads': settings.worker_threads,
        'png_engine': ('tifffile + imagecodecs' if output_format == 'tiff'
                       else 'libvips' if use_vips else 'Pillow'),
        'png_save_details': save_details,
        'output_megabytes_per_second': round(size/1_000_000/max(saving_seconds, .001), 1),
        'output_megapixels_per_second': round(width*height/1_000_000/max(saving_seconds, .001), 1),
        'order_check': order_check, 'analysis': analysis,
        'placements': [asdict(item) for _, item in planned],
        'rotation_count': sum(bool(item.rotation_degrees) for _, item in planned),
        'timings_seconds': {
            'reading': round(reading_seconds, 3),
            'combining': round(combining_seconds, 3),
            'saving_png': round(saving_seconds, 3),
            'output_validation': round(validation_seconds, 3),
            'total': round(total_seconds, 3),
        },
    }
    result.update(saving_metrics(baseline_height, height, settings.dpi))
    return result
