from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Iterable
from ..domain.models import LayoutSettings, ProgressCallback, mm_to_px
from automatic_print.layout_engine.output.output_name import planned_output_path
from ..diagnostics.dual_quality import dual_quality
from automatic_print.layout_engine.cutting.geometry.transition_marks import marked_height
from automatic_print.layout_engine.intake.preparation.batch_snapshot import batch_measurements
@batch_measurements
def generate_layout(
    image_paths: Iterable[Path], output_dir: Path, settings: LayoutSettings,
    progress: ProgressCallback | None = None, plan_ready=None, preview_only=False,
    analysis_ready=None, batch_name="", phase_ready=None,
    prepared_plan=None, filename_suffix="", prepared_gap_records=None,
    split_by_knife=False,
) -> dict:
    total_started = perf_counter()
    paths = list(image_paths)
    from automatic_print.layout_engine.output.output_sizes import enforce_output_compatibility
    settings, output_format_fallback = enforce_output_compatibility(settings, progress)
    if paths:
        label_batch_name = str(batch_name or settings.label_batch_name or paths[0].parent.name).strip()
        settings = replace(settings, label_batch_name=label_batch_name)
    from automatic_print.automation.api.s2b.metadata.prepare import prepare_s2b_metadata
    # A verified global plan already carries the batch metadata.  Segment
    # renderers must not re-query the same S2B batch once per output file.
    inherited_analysis = (prepared_plan or {}).get('analysis') or {}
    s2b_metadata = inherited_analysis.get('s2b_metadata') or []
    from automatic_print.layout_engine.intake.metadata.output_dpi import resolve_output_dpi
    settings = resolve_output_dpi(paths, settings, progress)
    from automatic_print.layout_engine.labeling.base.header_gap import prepare_paths
    if prepared_gap_records is None:
        if phase_ready and settings.membrane_gap_mm > 0:
            phase_ready('补足膜标签间距')
        from .preparation import gap_premeasure
        paths, settings, gap_records = prepare_paths(
            paths, settings, progress,
            premeasure=gap_premeasure(paths, settings),
        )
    else:
        gap_records = list(prepared_gap_records)
    if (settings.output_parts > 1 or split_by_knife) and not preview_only and prepared_plan is None:
        from automatic_print.layout_engine.rendering.storage.segmented_output import generate_segments
        return generate_segments(paths, output_dir, settings, progress,
                                 plan_ready, analysis_ready, batch_name, phase_ready,
                                 gap_records, split_by_knife=split_by_knife)
    if not s2b_metadata and prepared_plan is None:
        s2b_metadata = prepare_s2b_metadata(paths, settings, progress)
    if not preview_only:
        output_dir.mkdir(parents=True, exist_ok=True)
    reading_started = perf_counter()
    phase = phase_ready or (lambda name: None)
    phase('订单与尺码分析')
    from .analysis import analysis_callbacks
    effective, analysis, report, analyzed = analysis_callbacks(
        settings, gap_records, progress, analysis_ready,
        s2b_metadata, output_format_fallback,
    )
    if prepared_plan is None:
        from automatic_print.layout_engine.planning.zones.gap_fallback import plan_with_gap_fallback
        paths, settings, result = plan_with_gap_fallback(paths, settings, gap_records, report, analyzed)
        planned, labels, width, height, baseline_height = result
        effective[0] = replace(settings, cutter_knife_mm=effective[0].cutter_knife_mm)
    else:
        planned, labels, width, height, baseline_height = prepared_plan['plan']
        effective[0] = prepared_plan['settings']
        analysis[:] = [prepared_plan['analysis']]
        if output_format_fallback:
            analysis[-1]['output_format_fallback'] = output_format_fallback
    if s2b_metadata:
        analysis[-1]['s2b_metadata'] = s2b_metadata
    settings = effective[0]
    if settings.cutter_knife_change_gap_mm > 0:
        from automatic_print.layout_engine.cutting.geometry.knife_change_gap import apply_knife_change_gap
        result, knife_changes = apply_knife_change_gap(
            (planned, labels, width, height, baseline_height), settings)
        planned, labels, width, height, baseline_height = result
        analysis[-1]['knife_change_gap'] = knife_changes
    if settings.batch_end_block:
        width = mm_to_px(settings.media_width_mm,settings.dpi)
    if settings.fixed_output_width_mm > 0:
        fixed_width = mm_to_px(settings.fixed_output_width_mm, settings.dpi)
        if fixed_width > mm_to_px(settings.media_width_mm, settings.dpi):
            raise ValueError('输出画布宽度不能超过当前可排版宽度。')
        if width > fixed_width:
            raise ValueError('排版内容超过输出画布宽度，请增大画布宽度后重试。')
        width = fixed_width
    height = marked_height(planned, settings, width, height,
                           (prepared_plan or {}).get('end_notice', '批次结束'))
    phase('坐标与订单安全检查')
    from .validation import validate_plan
    warning, order_check, cut_check = validate_plan(
        paths, planned, settings, width, height, preview_only,
    )
    output_path, sizes = planned_output_path(
        output_dir, paths, planned, labels, settings, analysis[-1], batch_name,
        prepared_plan, filename_suffix,
    )
    quality = dual_quality(planned, settings, analysis[-1])
    from .analysis import emit_plan_ready
    emit_plan_ready(
        plan_ready, planned, labels, settings, order_check, analysis[-1],
        quality, baseline_height, height, width, warning, s2b_metadata,
    )
    if preview_only:
        from automatic_print.layout_engine.reporting.preview_result import build_preview_result
        return build_preview_result(
            output_path.name, planned, quality, sizes, settings, analysis[-1],
            gap_records, cut_check, order_check, width, height, baseline_height,
        )
    reading_seconds = perf_counter() - reading_started
    from .render_output import render_output
    rendered = render_output(
        planned, labels, width, height, settings, progress, cut_check,
        prepared_plan, output_path, phase,
    )
    (output_format, use_vips, save_details, combining_seconds,
     saving_seconds, output_validation_seconds, guide_spans, guide_boxes,
     missing_guides, transitions) = rendered
    filename = output_path.name
    phase('批次信息整理')
    from automatic_print.layout_engine.output.generation_result import build_result
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
        validation_seconds=output_validation_seconds, total_seconds=perf_counter() - total_started,
    )
    from automatic_print.layout_engine.labeling.base.header_gap import verify_records
    verify_records(gap_records)
    return result
