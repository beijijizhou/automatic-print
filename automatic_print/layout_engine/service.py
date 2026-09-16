from __future__ import annotations
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Iterable
from .models import LayoutSettings, ProgressCallback, mm_to_px
from .output_name import planned_output_path
from .dual_quality import dual_quality
from .marker_space import validate_embedded_marks
from .cut_validation import validate_cut_corridor, validate_canvas_pixels, validate_vips_output
from .order_validation import validate_order_placements
from .pillow_renderer import build_pillow_canvas
from .printed_guides import collect_guides, dot_boxes, paint_guides, validate_vips_canvas
from .planner import plan_layout
from .vips_renderer import available, build_vips_canvas, build_vips_rows
from .output_encoder import encoder_plan, save_output
from .transition_marks import marked_height, transition_rects, paint_transition_lines
from .marked_pixel_validation import validate_marked_pillow
from .batch_snapshot import batch_measurements
@batch_measurements
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
    total_started = perf_counter()
    paths = list(image_paths)
    if paths:
        label_batch_name = str(
            batch_name or settings.label_batch_name or paths[0].parent.name
        ).strip()
        settings = replace(settings, label_batch_name=label_batch_name)
    from ..automation.api.s2b.prepare import prepare_s2b_metadata
    s2b_metadata = prepare_s2b_metadata(paths, settings, progress)
    from .header_gap import prepare_paths
    if phase_ready and settings.membrane_gap_mm > 0:
        phase_ready('补足膜标签间距')
    paths, settings, gap_records = prepare_paths(paths, settings, progress)
    from .output_dpi import resolve_output_dpi
    settings = resolve_output_dpi(paths, settings, progress)
    if settings.output_parts > 1 and not preview_only and prepared_plan is None:
        from .segmented_output import generate_segments
        return generate_segments(paths, output_dir, settings, progress,
                                 plan_ready, analysis_ready, batch_name, phase_ready)
    if not preview_only:
        output_dir.mkdir(parents=True, exist_ok=True)
    reading_started = perf_counter()
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
        from .header_gap import annotate_analysis
        annotate_analysis(data, gap_records, settings, progress)
        analysis[:] = [data]
        if analysis_ready:
            analysis_ready(data)
    if prepared_plan is None:
        from .gap_fallback import plan_with_gap_fallback
        paths, settings, result = plan_with_gap_fallback(paths, settings, gap_records, report, analyzed)
        planned, labels, width, height, baseline_height = result
        effective[0] = replace(settings, cutter_knife_mm=effective[0].cutter_knife_mm)
    else:
        planned, labels, width, height, baseline_height = prepared_plan['plan']
        effective[0] = prepared_plan['settings']
        analysis[:] = [prepared_plan['analysis']]
    if s2b_metadata:
        analysis[-1]['s2b_metadata'] = s2b_metadata
    settings = effective[0]
    if settings.batch_end_block:
        width = mm_to_px(settings.media_width_mm,settings.dpi)
    height = marked_height(planned, settings, width, height,
                           (prepared_plan or {}).get('end_notice', '批次结束'))
    phase('坐标与订单安全检查')
    warning, order_check = "", {}
    try:
        order_check = validate_order_placements(paths, planned)
        cut_check = validate_cut_corridor(planned, settings, width)
        if settings.cutter_mode != 'free':
            validate_embedded_marks(planned, settings)
    except ValueError as error:
        if not preview_only:
            raise
        warning = f"仅供检查，禁止输出：{error}"
    output_path, sizes = planned_output_path(
        output_dir, paths, planned, labels, settings, analysis[-1], batch_name,
        prepared_plan, filename_suffix,
    )
    quality = dual_quality(planned, settings, analysis[-1])
    if plan_ready:
        from ..automation.api.s2b.prepare import metadata_warning_text
        metadata_warning = metadata_warning_text(s2b_metadata)
        visible_warning = "\n".join(filter(None, (warning, metadata_warning)))
        plan_ready({"planned": planned, "labels": labels, "settings": settings, "order_check": order_check, "analysis": analysis[-1], "dual_quality": quality,
                    "saved_meters": max(0,baseline_height-height)*25.4/settings.dpi/1000,
                    "canvas": (width, height, baseline_height),
                    "warning": visible_warning})
    if preview_only:
        from .preview_result import build_preview_result
        return build_preview_result(
            output_path.name, planned, quality, sizes, settings, analysis[-1],
            gap_records, cut_check, order_check, width, height, baseline_height,
        )
    reading_seconds = perf_counter() - reading_started
    combining_started = perf_counter()
    phase('图片准备与合成')
    output_format, streaming, use_vips = encoder_plan(settings, width, height)
    from .vips_renderer import demand_lock
    native_validation = use_vips or (settings.png_fast_encoding and available())
    with demand_lock if native_validation else nullcontext():
        row_streaming = streaming and use_vips
        if row_streaming:
            rows = build_vips_rows(planned, labels, width, settings, progress)
            canvas = None
        else:
            builder = build_vips_canvas if use_vips else build_pillow_canvas
            canvas = builder(planned, labels, (width, height), settings, progress)
        combining_seconds = perf_counter() - combining_started
        phase('合成像素安全检查')
        if not use_vips:
            validate_canvas_pixels(canvas, cut_check, progress)
        elif not streaming:
            validate_vips_canvas(canvas, cut_check)
        phase('膜标签与辅助线处理')
        guide_spans, missing_guides = collect_guides(planned, settings, progress)
        guide_boxes = list(dot_boxes(guide_spans, settings.dpi))
        transitions = transition_rects(planned, settings, width,
                                      (prepared_plan or {}).get('end_notice', '批次结束'))
        if not row_streaming:
            canvas = paint_guides(canvas, guide_boxes, use_vips)
            canvas = paint_transition_lines(canvas, transitions, use_vips)
            if not use_vips:
                validate_marked_pillow(
                    canvas, cut_check, guide_boxes, transitions, progress
                )
        filename = output_path.name
        saving_started = perf_counter()
        output_validation_seconds = 0.0
        phase('保存输出图片')
        if row_streaming:
            from .png_codecs.row_stream import save as save_rows
            save_details = save_rows(
                rows, output_path, width, height, settings,
                guide_boxes, transitions, progress,
            )
        else:
            save_details = save_output(
                canvas, output_path, settings, use_vips, progress)
        saving_seconds = perf_counter() - saving_started
        if streaming:
            from .png_codecs.streaming import validate_saved_output
            output_validation_seconds = validate_saved_output(
                output_path, width, height, cut_check, guide_boxes,
                transitions, progress, phase, save_details,
            )
        elif native_validation:
            phase('输出文件安全复核')
            validate_vips_output(output_path, cut_check, progress, guide_boxes, transitions)
        elif settings.png_fast_encoding and cut_check:
            from PIL import Image
            phase('输出文件安全复核')
            try:
                with Image.open(output_path) as saved:
                    validate_marked_pillow(saved, cut_check, guide_boxes, transitions, progress)
            except ValueError:
                output_path.rename(output_path.with_suffix('.禁止打印'))
                raise
        if native_validation:
            canvas = None
            import pyvips
            pyvips.cache_set_max(0)
    phase('批次信息整理')
    from .generation_result import build_result
    result = build_result(
        filename=filename, output_path=output_path, settings=settings,
        paths=paths, planned=planned, analysis=analysis[-1], quality=quality,
        sizes=sizes, gap_records=gap_records, cut_check=cut_check,
        order_check=order_check, guide_spans=guide_spans,
        guide_boxes=guide_boxes, missing_guides=missing_guides,
        transitions=transitions, width=width,
        height=height, baseline_height=baseline_height,
        output_format=output_format, use_vips=use_vips,
        save_details=save_details, reading_seconds=reading_seconds,
        combining_seconds=combining_seconds, saving_seconds=saving_seconds,
        validation_seconds=output_validation_seconds,
        total_seconds=perf_counter() - total_started,
    )
    from .header_gap import verify_records
    verify_records(gap_records)
    return result
