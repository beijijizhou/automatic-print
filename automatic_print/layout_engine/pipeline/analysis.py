"""Callbacks that attach shared preparation facts to layout analysis."""
from dataclasses import replace


def analysis_callbacks(
    settings, gap_records, progress, analysis_ready,
    s2b_metadata, output_format_fallback,
):
    effective, reports = [settings], []

    def report(stage, current, total, filename):
        if stage == '批次刀位已确定':
            effective[0] = replace(settings, cutter_knife_mm=current * 25.4 / total)
        if progress:
            progress(stage, current, total, filename)

    def analyzed(data):
        from automatic_print.layout_engine.labeling.base.header_gap import annotate_analysis
        annotate_analysis(data, gap_records, settings, progress)
        if s2b_metadata:
            data['s2b_metadata'] = s2b_metadata
        if output_format_fallback:
            data['output_format_fallback'] = output_format_fallback
        reports[:] = [data]
        if analysis_ready:
            analysis_ready(data)

    return effective, reports, report, analyzed


def emit_plan_ready(callback, planned, labels, settings, order_check, analysis,
                    quality, baseline_height, height, width, warning, metadata):
    if not callback:
        return
    from automatic_print.automation.api.s2b.metadata.prepare import metadata_warning_text
    metadata_warning = metadata_warning_text(metadata)
    callback({
        'planned': planned, 'labels': labels, 'settings': settings,
        'order_check': order_check, 'analysis': analysis,
        'dual_quality': quality,
        'saved_meters': max(0, baseline_height-height)*25.4/settings.dpi/1000,
        'canvas': (width, height, baseline_height),
        'warning': '\n'.join(filter(None, (warning, metadata_warning))),
        'blocking_warning': warning,
        'metadata_warning': metadata_warning,
    })
