from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Iterable

from .models import LayoutSettings, ProgressCallback
from .images import print_dimensions
from .labels import normalize_machine_number, format_label
from .output_name import label_output_name, unused_output_path
from .dual_quality import dual_quality
from .cut_validation import validate_cut_corridor, validate_canvas_pixels, validate_vips_output
from .metrics import saving_metrics
from .order_validation import validate_order_placements
from .pillow_renderer import build_pillow_canvas
from .printed_guides import collect_guides, dot_boxes, paint_guides, validate_vips_canvas
from .planner import plan_layout
from .save_progress import monitor_save
from .vips_renderer import available, build_vips_canvas
from .transition_marks import marked_height, transition_rects, paint_transition_lines
from .output_sizes import size_range_label
from .marked_pixel_validation import validate_marked_pillow


def png_engine_name() -> str:
    return "大图节省内存模式" if available() else "标准兼容模式"


def generate_layout(
    image_paths: Iterable[Path],
    output_dir: Path,
    settings: LayoutSettings,
    progress: ProgressCallback | None = None,
    plan_ready=None,
    preview_only=False,
    analysis_ready=None,
    batch_name="",
    phase_ready=None,
    prepared_plan=None,
    filename_suffix="",
) -> dict:
    if settings.output_parts > 1 and not preview_only and prepared_plan is None:
        from .segmented_output import generate_segments
        return generate_segments(list(image_paths), output_dir, settings, progress,
                                 plan_ready, analysis_ready, batch_name, phase_ready)
    total_started = perf_counter()
    if not preview_only:
        output_dir.mkdir(parents=True, exist_ok=True)
    reading_started = perf_counter()
    paths = list(image_paths)
    phase = phase_ready or (lambda name: None)
    phase('订单与尺码分析')
    effective = [settings]
    def report(stage, current, total, filename):
        if stage == "批次刀位已确定":
            effective[0] = replace(settings, cutter_knife_mm=current*25.4/total)
        if progress:
            progress(stage, current, total, filename)
    analysis = []
    def analyzed(data):
        analysis[:] = [data]
        if analysis_ready:
            analysis_ready(data)
    if prepared_plan is None:
        planned, labels, width, height, baseline_height = plan_layout(
            paths, settings, report, analysis_ready=analyzed)
    else:
        planned, labels, width, height, baseline_height = prepared_plan['plan']
        effective[0] = prepared_plan['settings']
        analysis[:] = [prepared_plan['analysis']]
    settings = effective[0]
    height = marked_height(planned, settings, width, height)
    phase('坐标与订单安全检查')
    warning, order_check = "", {}
    try:
        order_check = validate_order_placements(paths, planned)
        cut_check = validate_cut_corridor(planned, settings, width)
    except ValueError as error:
        if not preview_only:
            raise
        warning = f"仅供检查，禁止输出：{error}"
    label_text = labels.get(1) or format_label(settings.label_text_template, 1, paths[0],
                    datetime.now().astimezone(), settings.label_date_format, settings.machine_number)
    if settings.label_machine_enabled or settings.label_sequence_enabled:
        label_text = format_label(settings.label_text_template, 1, paths[0],
            datetime.now().astimezone(), settings.label_date_format, settings.machine_number)
    sizes = size_range_label([path for path, p in sorted(planned, key=lambda entry: (entry[1].row_y_px, entry[1].x_px))])
    size_suffix = f' {sizes}' if sizes else ''
    zones = {p.cut_zone for _, p in planned}
    zone_suffix = ' 旋转区' if zones == {'旋转区'} else ' 常规+旋转区' if '旋转区' in zones else ''
    output_path = unused_output_path(output_dir, label_output_name(label_text+size_suffix+zone_suffix+filename_suffix, batch_name))
    quality = dual_quality(planned, settings)
    if plan_ready:
        plan_ready({"planned": planned, "labels": labels, "settings": settings, "warning": warning, "order_check": order_check, "analysis": analysis[-1], "dual_quality": quality,
                    "saved_meters": max(0,baseline_height-height)*25.4/settings.dpi/1000,
                    "canvas": (width, height, baseline_height)})
    if preview_only:
        return {"preview_only": True, "width_px": width, "height_px": height, "analysis": analysis[-1]}
    reading_seconds = perf_counter() - reading_started

    combining_started = perf_counter()
    phase('图片准备与合成')
    use_vips = settings.png_engine == "libvips" and available()
    builder = build_vips_canvas if use_vips else build_pillow_canvas
    canvas = builder(
        planned, labels, (width, height), settings, progress
    )
    combining_seconds = perf_counter() - combining_started
    phase('合成像素安全检查')
    if not use_vips:
        validate_canvas_pixels(canvas, cut_check, progress)
    else:
        validate_vips_canvas(canvas, cut_check)
    phase('二维码与辅助线处理')
    guide_spans, missing_guides = collect_guides(planned, settings, progress)
    guide_boxes = list(dot_boxes(guide_spans, settings.dpi))
    canvas = paint_guides(canvas, guide_boxes, use_vips)
    transitions = transition_rects(planned, settings, width,
                                  (prepared_plan or {}).get('end_notice', '批次结束'))
    canvas = paint_transition_lines(canvas, transitions, use_vips)
    if not use_vips:
        validate_marked_pillow(canvas, cut_check, guide_boxes, transitions, progress)

    filename = output_path.name
    saving_started = perf_counter()
    phase('保存输出图片')
    with monitor_save(output_path, progress):
        if use_vips:
            canvas.pngsave(
                str(output_path),
                compression=settings.png_compression_level,
                interlace=False,
            )
        else:
            canvas.save(
                output_path,
                dpi=(settings.dpi, settings.dpi),
                compress_level=settings.png_compression_level,
            )
            canvas.close()
    saving_seconds = perf_counter() - saving_started
    if use_vips:
        phase('输出文件安全复核')
        validate_vips_output(output_path, cut_check, progress, guide_boxes, transitions)
    phase('批次信息整理')
    size = output_path.stat().st_size
    result = {
        "filename": filename,
        "dual_quality": quality,
        "size_range": sizes, "output_dpi": settings.dpi,
        "transition_marks": transitions,
        "rotation_marker_shift_mm": settings.rotation_marker_shift_mm,
        "machine_number": normalize_machine_number(settings.machine_number),
        "cutter_mode": settings.cutter_mode,
        'platform_name': settings.platform_name,
        'label_sequence_enabled': settings.label_sequence_enabled,
        "cut_corridor": cut_check,
        "printed_guides": {"span_count": len(guide_spans), "dot_count": len(guide_boxes),
                           "missing_qr": missing_guides},
        "cutter_knife_mm": settings.cutter_knife_mm if settings.cutter_mode == "dual" else None,
        "cutter_safety_mm": settings.cutter_safety_mm,
        "right_marker_mm": (
            settings.cutter_knife_mm + settings.cutter_safety_mm
            + settings.cutter_marker_offset_mm
            if settings.cutter_mode == "dual" else None
        ),
        "source_dimensions": [
            {"source": path.name, **asdict(print_dimensions(path, settings.dpi))}
            for path in paths
        ],
        "width_px": width,
        "height_px": height,
        "width_mm": round(width * 25.4 / settings.dpi, 1),
        "maximum_width_mm": settings.media_width_mm,
        "trimmed_right_mm": round(
            max(0, settings.media_width_mm - width * 25.4 / settings.dpi),
            1,
        ),
        "height_mm": round(height * 25.4 / settings.dpi, 1),
        "file_size_bytes": size,
        "png_compression_level": settings.png_compression_level,
        "png_engine": "libvips" if use_vips else "Pillow",
        "output_megabytes_per_second": round(
            size / 1_000_000 / max(saving_seconds, 0.001), 1
        ),
        "output_megapixels_per_second": round(
            width * height / 1_000_000 / max(saving_seconds, 0.001), 1
        ),
        "order_check": order_check, "analysis": analysis[-1],
        "placements": [asdict(item) for _, item in planned],
        "rotation_count": sum(
            bool(item.rotation_degrees) for _, item in planned
        ),
        "timings_seconds": {
            "reading": round(reading_seconds, 3),
            "combining": round(combining_seconds, 3),
            "saving_png": round(saving_seconds, 3),
            "total": round(perf_counter() - total_started, 3),
        },
    }
    result.update(saving_metrics(baseline_height, height, settings.dpi))
    return result
