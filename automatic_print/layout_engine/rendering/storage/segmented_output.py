"""Partition one verified global plan, never independently re-plan orders."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from threading import RLock
from time import perf_counter

from automatic_print.layout_engine.domain.models import mm_to_px, MAX_SAVE_PARALLELISM
from automatic_print.layout_engine.orders.order_groups import order_key
from automatic_print.layout_engine.reporting.operation_timing import OperationTiming
from automatic_print.layout_engine.reporting.metrics import saving_metrics
from automatic_print.layout_engine.output.output_sizes import size_range_label
from automatic_print.layout_engine.output.output_name import production_quantity


def partition_plan(planned, count):
    orders = {}
    for path, p in planned:
        orders.setdefault(order_key(path), []).append((path, p))
    blocks = []
    for members in orders.values():
        start = min(p.row_y_px for _, p in members)
        end = max(p.row_y_px+p.footprint_height_px for _, p in members)
        if blocks and start < blocks[-1][1]:
            old_start, old_end, old_members = blocks[-1]
            blocks[-1] = old_start, max(end, old_end), old_members+members
        else:
            blocks.append((start, end, members))
    count = min(max(1, count), len(blocks))
    partitions, index = [], 0
    for part in range(count):
        remaining = count-part
        target = sum(b[1]-b[0] for b in blocks[index:])/remaining
        end, weight = index+1, blocks[index][1]-blocks[index][0]
        while end < len(blocks)-(remaining-1):
            next_weight = blocks[end][1]-blocks[end][0]
            if abs(weight+next_weight-target) >= abs(weight-target):
                break
            weight += next_weight
            end += 1
        members = {path for b in blocks[index:end] for path, _ in b[2]}
        partitions.append([(path, p) for path, p in planned if path in members])
        index = end
    return partitions


def shift_part(members, margin):
    start = min(p.row_y_px for _, p in members)
    end = max(p.row_y_px+p.footprint_height_px for _, p in members)
    offset = start-margin
    shifted = [(path, replace(p, y_px=p.y_px-offset, row_y_px=p.row_y_px-offset,
        number_y_px=p.number_y_px-offset, color_block_y_px=p.color_block_y_px-offset,
        platform_y_px=p.platform_y_px-offset))
        for path, p in members]
    return shifted, end-start+2*margin


def save_concurrency(settings, width, plans, planned):
    parallel = min(max(1, settings.save_parallelism), MAX_SAVE_PARALLELISM, len(plans))
    buffers = settings.worker_threads*max(p.width_px*p.height_px*4 for _, p in planned)
    estimate = sum(sorted((width*height*4 for _, height in plans), reverse=True)[:parallel])+buffers
    if not settings.save_memory_unlimited and estimate > max(128, settings.save_memory_mb)*1024*1024:
        parallel = 1
    return parallel, estimate


def generate_segments(paths, output_dir, settings, progress, plan_ready,
                      analysis_ready, batch_name, phase_ready):
    from automatic_print.layout_engine.pipeline.service import generate_layout
    started = perf_counter()
    snapshots = []
    base = replace(settings, output_parts=1)
    def ready(payload):
        snapshots.append(payload)
        if plan_ready:
            plan_ready(payload)
    generate_layout(paths, output_dir, base, progress, ready, preview_only=True,
                    analysis_ready=analysis_ready, phase_ready=phase_ready, batch_name=batch_name)
    payload = snapshots[0]
    # API/metadata warnings remain visible but are recoverable.  Only a real
    # geometry or cutter-safety failure may block segmented production output.
    blocking_warning = payload.get('blocking_warning', payload['warning'])
    if blocking_warning:
        raise ValueError(blocking_warning)
    base = payload['settings']
    if settings.batch_footer_enabled:
        from automatic_print.layout_engine.output.batch_footer import footer_text
        base = replace(base, batch_footer_context=footer_text(payload['planned'], base, '整批信息'))
    width, _, baseline = payload['canvas']
    parts = partition_plan(payload['planned'], settings.output_parts)
    from automatic_print.layout_engine.labeling.markers.left_marker import head_margin
    margin = head_margin(settings)
    plans = [shift_part(members, margin) for members in parts]
    parallel, estimate = save_concurrency(settings, width, plans, payload['planned'])
    if progress:
        budget = '不限制内存预算' if settings.save_memory_unlimited else f'内存预算 {settings.save_memory_mb} 兆字节'
        progress('分段输出', 0, len(parts), f'{len(parts)} 个文件 · 同时处理 {parallel} 段 · {budget} · 沿用整批刀位')
    if phase_ready:
        phase_ready('分段合成、安全检查与保存')
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = '.tif' if settings.output_format.lower() == 'tiff' else '.png'
    existing = set(output_dir.glob('*'+suffix))
    lock, counts, results = RLock(), {}, {}
    reading = perf_counter()-started
    rendering = perf_counter()
    batch_quantity = production_quantity(paths, payload['analysis'])
    def render(index):
        members, height = plans[index]
        end_notice = '批次结束' if index == len(parts)-1 else '分段结束'
        if index < len(parts)-1 and members[-1][1].cut_zone != plans[index+1][0][0][1].cut_zone:
            end_notice += ' / 下一段进入旋转区换刀'
        timer = OperationTiming()
        def report(stage, current, total, filename):
            if progress:
                with lock:
                    if stage == '合成图片':
                        counts[index] = current
                        progress(stage, sum(counts.values()), len(paths), filename)
                    else:
                        progress(stage, current, total, f'第{index+1:03d}段 · {filename}')
        result = generate_layout([path for path, _ in members], output_dir,
            replace(base, worker_threads=max(1, settings.worker_threads//parallel),
                    batch_end_block=base.batch_end_block and index == len(parts)-1), report,
            batch_name=batch_name, phase_ready=timer.phase,
            filename_suffix=f' 第{index+1:03d}段', prepared_plan={
                'plan': (members, payload['labels'], width, height, height),
                'settings': replace(base, worker_threads=max(1, settings.worker_threads//parallel),
                                    batch_end_block=base.batch_end_block and index == len(parts)-1),
                'analysis': payload['analysis'], 'end_notice': end_notice,
                'batch_quantity': batch_quantity})
        result['operation_timings'] = timer.finish()
        result['segment_index'] = index+1
        return result
    try:
        if parallel == 1:
            for index in range(len(parts)):
                results[index] = render(index)
        else:
            with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix='segment-save') as pool:
                futures = {pool.submit(render, index): index for index in range(len(parts))}
                for future in as_completed(futures):
                    results[futures[future]] = future.result()
    except BaseException:
        # Keep unfinished files recoverable, but never leave them print-labelled.
        for path in set(output_dir.glob('*'+suffix))-existing:
            target, suffix = path.with_suffix('.生成未完成'), 2
            while target.exists():
                target = path.with_name(f'{path.stem} ({suffix}).生成未完成')
                suffix += 1
            path.rename(target)
        raise
    wall = perf_counter()-rendering
    ordered = [results[i] for i in range(len(parts))]
    total_height = sum(r['height_px'] for r in ordered)
    total_size = sum(r['file_size_bytes'] for r in ordered)
    result = dict(ordered[0])
    result.update(parts=ordered, files=[r['filename'] for r in ordered],
        segment_count=len(parts), actual_save_parallelism=parallel,
        save_memory_unlimited=settings.save_memory_unlimited,
        estimated_parallel_memory_mb=round(estimate/1024/1024, 1),
        placements=[dict(p, output_filename=r['filename'], segment_index=r['segment_index'])
                    for r in ordered for p in r['placements']],
        analysis=payload['analysis'], order_check=payload['order_check'],
        size_range=size_range_label([path for path, p in sorted(payload['planned'], key=lambda entry: (entry[1].row_y_px, entry[1].x_px))]),
        height_px=total_height, height_mm=round(total_height*25.4/settings.dpi, 1),
        file_size_bytes=total_size, rotation_count=sum(r['rotation_count'] for r in ordered),
        cut_corridor={'segments': [r['cut_corridor'] for r in ordered],
                      'pixel_verified': all(not r['cut_corridor'] or r['cut_corridor'].get('pixel_verified') for r in ordered)},
        timings_seconds={'reading': reading, 'combining': 0, 'saving_png': wall,
                         'total': perf_counter()-started})
    result['dual_quality'] = payload.get('dual_quality', {})
    result['source_dimensions'] = [d for part in ordered for d in part['source_dimensions']]
    result['printed_guides'] = {
        'span_count': sum(r['printed_guides']['span_count'] for r in ordered),
        'dot_count': sum(r['printed_guides']['dot_count'] for r in ordered),
        'missing_qr': [name for r in ordered for name in r['printed_guides']['missing_qr']]}
    result['transition_marks'] = [dict(r, filename=part['filename'])
                                  for part in ordered for r in part['transition_marks']]
    result['output_megabytes_per_second'] = round(total_size/1_000_000/max(wall, .001), 1)
    result.update(saving_metrics(baseline, total_height, settings.dpi))
    return result
