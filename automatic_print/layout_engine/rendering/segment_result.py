"""Assemble one immutable result from independently saved segments."""


def build_segment_result(ordered, payload, settings, gap_records, parallel,
                         process_safe, estimate, wall, reading, started):
    from pathlib import Path
    from time import perf_counter
    from automatic_print.layout_engine.output.output_sizes import size_range_label
    from automatic_print.layout_engine.reporting.metrics import saving_metrics

    total_height = sum(row['height_px'] for row in ordered)
    total_size = sum(row['file_size_bytes'] for row in ordered)
    result = dict(ordered[0])
    result.update(
        parts=ordered, files=[row['filename'] for row in ordered],
        segment_count=len(ordered), actual_save_parallelism=parallel,
        save_memory_unlimited=settings.save_memory_unlimited,
        save_execution=('独立进程并行' if process_safe else
                        '单进程' if parallel == 1 else '线程并行'),
        estimated_parallel_memory_mb=round(estimate/1024/1024, 1),
        placements=[dict(p, output_filename=row['filename'],
                         segment_index=row['segment_index'])
                    for row in ordered for p in row['placements']],
        header_gap=list(gap_records), analysis=payload['analysis'],
        order_check=payload['order_check'],
        size_range=size_range_label([
            path for path, _p in sorted(
                payload['planned'], key=lambda entry: (
                    entry[1].row_y_px, entry[1].x_px,
                ),
            )
        ]),
        height_px=total_height,
        height_mm=round(total_height*25.4/settings.dpi, 1),
        file_size_bytes=total_size,
        rotation_count=sum(row['rotation_count'] for row in ordered),
        cut_corridor={
            'segments': [row['cut_corridor'] for row in ordered],
            'pixel_verified': all(
                not row['cut_corridor']
                or row['cut_corridor'].get('pixel_verified')
                for row in ordered
            ),
        },
        timings_seconds={'reading': reading, 'combining': 0,
                         'saving_png': wall,
                         'total': perf_counter()-started},
    )
    result['dual_quality'] = payload.get('dual_quality', {})
    result['source_dimensions'] = [
        value for row in ordered for value in row['source_dimensions']
    ]
    result['printed_guides'] = {
        'span_count': sum(row['printed_guides']['span_count'] for row in ordered),
        'dot_count': sum(row['printed_guides']['dot_count'] for row in ordered),
        'missing_qr': [name for row in ordered
                       for name in row['printed_guides']['missing_qr']],
    }
    result['transition_marks'] = [
        dict(value, filename=row['filename']) for row in ordered
        for value in row['transition_marks']
    ]
    result['output_megabytes_per_second'] = round(
        total_size/1_000_000/max(wall, .001), 1,
    )
    result.update(saving_metrics(payload['canvas'][2], total_height, settings.dpi))
    return result
