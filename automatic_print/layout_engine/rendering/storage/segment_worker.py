"""Pickle-safe segment renderer for isolated native image pipelines."""
from dataclasses import replace


def render_segment_job(
    index, total, members, height, output_dir, settings, batch_name,
    labels, width, analysis, end_notice, batch_quantity, progress=None,
):
    from automatic_print.layout_engine.pipeline.service import generate_layout
    from automatic_print.layout_engine.reporting.operation_timing import OperationTiming

    timer = OperationTiming()
    result = generate_layout(
        [path for path, _placement in members],
        output_dir,
        settings,
        progress=progress,
        batch_name=batch_name,
        phase_ready=timer.phase,
        filename_suffix=f' 第{index + 1:03d}段',
        prepared_plan={
            'plan': (members, labels, width, height, height),
            'settings': settings,
            'analysis': analysis,
            'end_notice': end_notice,
            'batch_quantity': batch_quantity,
        },
        prepared_gap_records=(),
    )
    result['operation_timings'] = timer.finish()
    result['segment_index'] = index + 1
    return result


def segment_settings(base, worker_threads, final_segment):
    return replace(
        base,
        worker_threads=max(1, worker_threads),
        batch_end_block=base.batch_end_block and final_segment,
    )
