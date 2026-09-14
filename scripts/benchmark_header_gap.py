"""Independent production-file benchmark; verification is outside generation time."""
import argparse
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
import pyvips
from automatic_print import __version__
from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine import header_gap
from automatic_print.layout_engine.printed_guides import vips_corridor_is_clear


def verify_copies(records):
    count = 0
    for record in records:
        if not record['added_px']:
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


def run(source, output, cache, stack_platform=False):
    paths = sorted(source.glob('*.png'))
    if not paths:
        raise ValueError('源目录没有PNG')
    header_gap.cache_root = lambda: cache
    settings = LayoutSettings(media_width_mm=580, cutter_mode='dual', cutter_auto_knife=True,
        follow_source_dpi=True, membrane_gap_mm=40, png_streaming=True,
        cutter_left_marker_external=True, cutter_left_marker_lift_mm=1.5,
        cutter_knife_dots=False, preserve_header_gap=True, cutter_compare_whole_rotation=True,
        cutter_tail_rotation=True, png_engine='libvips', platform_name='隆丰',
        platform_font_height_mm=8, label_text_template='CY 1001Mt26',
        label_machine_enabled=True, label_sequence_enabled=True, compare_film_sizes=True,
        platform_below_marker=stack_platform)
    started = perf_counter()
    result = generate_layout(paths, output, settings, batch_name=source.name)
    generation = perf_counter()-started
    print(f'生成：{generation:.3f}秒', flush=True)
    started = perf_counter()
    copied = verify_copies(result['header_gap'])
    pixels = perf_counter()-started
    print(f'间距副本全部原像素复核：{pixels:.3f}秒', flush=True)
    started = perf_counter()
    image = pyvips.Image.new_from_file(str(output/result['filename']), access='random')
    zones = result['cut_corridor'].get('zones', [result['cut_corridor']])
    for zone in zones:
        if not vips_corridor_is_clear(image, zone):
            raise ValueError('保存后整批刀位通道不透明')
    corridor = perf_counter()-started
    report = dict(batch=source.name, version=__version__, images=len(paths),
        changed_images=copied, unchanged_images=len(paths)-copied,
        generation_seconds=generation, source_copy_check_seconds=pixels,
        saved_corridor_check_seconds=corridor, zones=len(zones),
        save_seconds=result['timings_seconds']['saving_png'],
        width_px=result['width_px'], height_px=result['height_px'], dpi=result['output_dpi'],
        settings=asdict(settings), file_size_bytes=result['file_size_bytes'],
        generation_includes_independent_checks=False,
        source_copy_pixels_exact=True, saved_corridors_clear=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    (output/'独立基准测试.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--stack-platform', action='store_true')
    args = parser.parse_args()
    run(args.source, args.output, args.cache, args.stack_platform)
