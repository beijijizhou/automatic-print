"""Independent production-file benchmark; verification is outside generation time."""
import argparse
from dataclasses import asdict
from pathlib import Path
from random import Random
from math import ceil
from time import perf_counter
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
import pyvips
from automatic_print import __version__
from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.labeling.base import header_gap
from automatic_print.layout_engine.cutting.geometry.printed_guides import vips_corridor_is_clear
from automatic_print.layout_engine.reporting.operation_timing import OperationTiming, PROGRESS_PHASES


def verify_copies(records):
    count = 0
    for record in records:
        if not record['added_px']:
            continue
        if record.get('virtual_gap'):
            with Image.open(record['source']) as original:
                dpi = original.info['dpi'][1]
                with original.convert('RGBA') as rgba:
                    alpha = np.asarray(rgba.getchannel('A'))
                occupied = alpha.max(axis=1) > 0
                following = np.flatnonzero(occupied[record['split_px']:])
                existing = int(following[0]) if len(following) else original.height-record['split_px']
                final_px = existing + record['added_px']
                required_px = ceil(record['minimum_mm'] * dpi / 25.4)
                if final_px < required_px:
                    raise ValueError(f"{record['filename']}：虚拟间距不足40毫米")
            count += 1
            continue
        with Image.open(record['source']) as original, Image.open(record['prepared']) as prepared:
            split, added = record['split_px'], record['added_px']
            for top in range(0, original.height, 128):
                end = min(original.height, top+128)
                sections = [(top, split), (split, end)] if top < split < end else [(top, end)]
                for a, b in sections:
                    shift = added if a >= split else 0
                    with original.crop((0, a, original.width, b)) as x:
                        with prepared.crop((0, a+shift, original.width, b+shift)) as y:
                            if not np.array_equal(np.asarray(x), np.asarray(y)):
                                raise ValueError(f"{record['filename']}：间距副本原像素不一致")
        count += 1
    return count


def run(
    source, output, cache, stack_platform=False, output_format='png',
    independent_checks=True, workers=4, limit=None, seed=20260917,
    output_parts=1, unlimited_memory=True,
    save_parallelism=4,
):
    paths = sorted(source.glob('*.png'))
    if not paths:
        raise ValueError('源目录没有PNG')
    if limit and len(paths) > limit:
        paths = sorted(Random(seed).sample(paths, limit))
    header_gap.cache_root = lambda: cache
    from automatic_print.layout_engine.planning.cache import plan_cache
    from automatic_print.layout_engine.measurement import measurement_cache
    plan_cache.cache_directory = lambda: cache
    measurement_cache.cache_directory = lambda: cache
    settings = LayoutSettings(media_width_mm=580, cutter_mode='dual', cutter_auto_knife=True,
        follow_source_dpi=True, membrane_gap_mm=40, png_streaming=True,
        cutter_left_marker_external=True, cutter_left_marker_lift_mm=1.5,
        cutter_knife_dots=False, preserve_header_gap=True, cutter_compare_whole_rotation=True,
        cutter_tail_rotation=True, png_engine='libvips', platform_name='Haloo',
        output_format=output_format,
        worker_threads=workers, output_parts=output_parts,
        save_memory_unlimited=unlimited_memory,
        save_parallelism=save_parallelism,
        platform_font_height_mm=8, label_text_template='CY 1001Mt26',
        label_machine_enabled=True, label_sequence_enabled=True, compare_film_sizes=True,
        platform_below_marker=stack_platform)
    timer = OperationTiming()
    timer.phase('开始生成')
    def progress(stage, current, total, detail):
        if stage in PROGRESS_PHASES:
            timer.phase(PROGRESS_PHASES[stage])
    started = perf_counter()
    result = generate_layout(
        paths, output, settings, progress=progress, batch_name=source.name,
        phase_ready=timer.phase,
    )
    operation_timings = timer.finish()
    generation = perf_counter()-started
    print(f'生成：{generation:.3f}秒', flush=True)
    records = result['header_gap']
    changed = sum(bool(record.get('added_px')) for record in records)
    gap_verified = sum(
        not record.get('warning')
        and record.get('final_gap_mm', record.get('minimum_mm', 0))
            >= record.get('minimum_mm', 0)
        for record in records
    )
    copied, pixels, corridor = 0, 0.0, 0.0
    from automatic_print.layout_engine.cutting.validation.cut_validation import corridor_checks
    corridors = corridor_checks(result['cut_corridor'])
    if independent_checks:
        started = perf_counter()
        copied = verify_copies(result['header_gap'])
        pixels = perf_counter()-started
        print(f'间距副本全部原像素复核：{pixels:.3f}秒', flush=True)
        started = perf_counter()
        for part in result.get('parts', (result,)):
            image = pyvips.Image.new_from_file(str(output/part['filename']), access='random')
            for item in corridor_checks(part['cut_corridor']):
                if not vips_corridor_is_clear(image, item):
                    raise ValueError(f"{part['filename']}：保存后刀位通道不透明")
        corridor = perf_counter()-started
    report = dict(batch=source.name, version=__version__, images=len(paths),
        changed_images=changed, unchanged_images=len(paths)-changed,
        forty_mm_verified_images=gap_verified,
        gap_warning_images=sum(bool(record.get('warning')) for record in records),
        generation_seconds=generation, source_copy_check_seconds=pixels,
        saved_corridor_check_seconds=corridor, zones=len(corridors),
        save_seconds=result['timings_seconds']['saving_png'],
        generation_timings=result['timings_seconds'],
        operation_timings=operation_timings,
        save_details=result['png_save_details'],
        width_px=result['width_px'], height_px=result['height_px'], dpi=result['output_dpi'],
        settings=asdict(settings), file_size_bytes=result['file_size_bytes'],
        generation_includes_independent_checks=False,
        independent_checks_run=independent_checks,
        source_copy_pixels_exact=independent_checks,
        saved_corridors_clear=independent_checks)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    (output/'独立基准测试.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--stack-platform', action='store_true')
    parser.add_argument('--format', choices=('png', 'tiff'), default='png')
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--seed', type=int, default=20260917)
    parser.add_argument('--parts', type=int, default=1)
    parser.add_argument('--parallel', type=int, default=4)
    parser.add_argument('--limit-memory', dest='unlimited_memory', action='store_false')
    parser.add_argument('--unlimited-memory', dest='unlimited_memory', action='store_true')
    parser.set_defaults(unlimited_memory=True)
    args = parser.parse_args()
    run(
        args.source, args.output, args.cache, args.stack_platform, args.format,
        not args.quick, args.workers, args.limit, args.seed, args.parts,
        args.unlimited_memory, args.parallel,
    )
