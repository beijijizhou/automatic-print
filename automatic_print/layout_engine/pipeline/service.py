from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Iterable
from ..domain.models import LayoutSettings, ProgressCallback, mm_to_px
from automatic_print.layout_engine.output.output_name import planned_output_path
from ..diagnostics.dual_quality import dual_quality
from automatic_print.layout_engine.labeling.markers.marker_space import validate_embedded_marks
from automatic_print.layout_engine.cutting.validation.cut_validation import validate_cut_corridor
from automatic_print.layout_engine.cutting.validation.order_validation import validate_order_placements
from automatic_print.layout_engine.cutting.geometry.transition_marks import marked_height
from automatic_print.layout_engine.intake.preparation.batch_snapshot import batch_measurements
@batch_measurements
def generate_layout(
    image_paths: Iterable[Path], output_dir: Path, settings: LayoutSettings,
    progress: ProgressCallback | None = None, plan_ready=None, preview_only=False,
    analysis_ready=None, batch_name="", phase_ready=None,
    prepared_plan=None, filename_suffix="", prepared_gap_records=None,
) -> dict:
    total_started = perf_counter()
    preview_timer = None
    if preview_only:
        from automatic_print.layout_engine.reporting.operation_timing import (
            OperationTiming, PROGRESS_PHASES,
        )
        preview_timer = OperationTiming()
        original_progress = progress

        def preview_progress(stage, current, total, name):
            mapped = PROGRESS_PHASES.get(stage)
            if mapped:
                preview_timer.phase(mapped)
            if original_progress:
                original_progress(stage, current, total, name)

        progress = preview_progress

        original_phase_ready = phase_ready

        def notify_phase(name):
            preview_timer.phase(name)
            if original_phase_ready:
                original_phase_ready(name)

        phase_ready = notify_phase
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
        premeasure = None
        from automatic_print.layout_engine.labeling.gap.virtual import enabled as virtual_gap
        if settings.membrane_gap_mm > 0 and virtual_gap(settings):
            from automatic_print.layout_engine.intake.preparation.item_factory import read_items
            from automatic_print.layout_engine.measurement.measurement_session import resolved_name

            def premeasure(index, path, local_settings):
                measured = replace(
                    local_settings,
                    sequence_numbers=((resolved_name(path), index + 1),),
                    label_sequence_total=(local_settings.label_sequence_total
                                          or len(paths)),
                )
                read_items([path], measured, None)

        paths, settings, gap_records = prepare_paths(
            paths, settings, progress, premeasure=premeasure,
        )
    else:
        gap_records = list(prepared_gap_records)
    if settings.output_parts > 1 and not preview_only and prepared_plan is None:
        from automatic_print.layout_engine.rendering.storage.segmented_output import generate_segments
        return generate_segments(paths, output_dir, settings, progress,
                                 plan_ready, analysis_ready, batch_name, phase_ready,
                                 gap_records)
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
    height = marked_height(planned, settings, width, height,
                           (prepared_plan or {}).get('end_notice', '批次结束'))
    phase('坐标与订单安全检查')
    warning, order_check, cut_check = "", {}, {}
    try:
        order_check = validate_order_placements(paths, planned)
        cut_check = validate_cut_corridor(
            planned, settings, width, canvas_height=height,
        )
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
        from automatic_print.automation.api.s2b.metadata.prepare import metadata_warning_text
        metadata_warning = metadata_warning_text(s2b_metadata)
        visible_warning = "\n".join(filter(None, (warning, metadata_warning)))
        plan_ready({"planned": planned, "labels": labels, "settings": settings, "order_check": order_check, "analysis": analysis[-1], "dual_quality": quality,
                    "saved_meters": max(0,baseline_height-height)*25.4/settings.dpi/1000,
                    "canvas": (width, height, baseline_height),
                    "warning": visible_warning,
                    "blocking_warning": warning,
                    "metadata_warning": metadata_warning})
    if preview_only:
        from automatic_print.layout_engine.reporting.preview_result import build_preview_result
        phase('批次信息整理')
        result = build_preview_result(
            output_path.name, planned, quality, sizes, settings, analysis[-1],
            gap_records, cut_check, order_check, width, height, baseline_height,
        )
        result['operation_timings'] = preview_timer.finish()
        return result
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
