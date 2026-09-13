from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.layout_engine.cut_validation import validate_cut_corridor
from automatic_print.layout_engine.transition_marks import transition_rects
from automatic_print.layout_engine.output_sizes import size_range_label
from automatic_print.layout_engine.segmented_output import save_concurrency


def sources(tmp_path):
    paths = []
    for order, size, width, height in [('B1', 'L', 100, 300), ('B2', 'S', 200, 150)]:
        for side in (1, 2):
            path = tmp_path/f'{order}-1-T-Black-{size}-NO1-{side}.png'
            Image.new('RGBA', (width, height), 'blue').save(path, dpi=(25.4, 25.4))
            paths.append(path)
    return paths


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('parts', [1, 2])
def test_full_outputs_have_exact_red_lines_and_shifted_rotation_markers(tmp_path, engine, parts):
    paths = sources(tmp_path)
    settings = LayoutSettings(dpi=25.4, margin_mm=0, media_width_mm=600,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=True,
        number_images=True, rotation_marker_shift_mm=2, transition_lines=True,
        output_parts=parts, png_engine=engine, save_memory_unlimited=True)
    result = generate_layout(paths, tmp_path/'out', settings)
    for part in result.get('parts') or [result]:
        assert part['size_range'] in part['filename']
        assert part['transition_marks']
        with Image.open(tmp_path/'out'/part['filename']) as image:
            for mark in part['transition_marks']:
                assert image.getpixel((image.width//2, mark['y'])) == (255, 0, 0, 255)
                assert image.getpixel((0, mark['y'])) == (255, 0, 0, 255)
                assert mark['y']+mark['height'] <= image.height
            for p in part['placements']:
                if p['cut_zone'] == '旋转区':
                    assert p['color_block_x_px'] == 2
                    assert p['number_x_px'] == 2
                    assert image.getpixel((0, p['color_block_y_px']))[3] == 0
                    assert image.getpixel((2, p['color_block_y_px'])) == (255, 0, 0, 255)
            for zone in part['cut_corridor'].get('zones', [part['cut_corridor']]):
                assert zone['pixel_verified']
                left, right = zone['safe_left_px'], zone['safe_right_px']
                top, end = zone.get('start_y_px', 0), zone.get('end_y_px', image.height)
                marks = {y for r in part['transition_marks'] for y in range(r['y'], r['y']+r['height'])}
                for y in range(top, end):
                    alpha = image.crop((left, y, right, y+1)).getchannel('A').getextrema()[1]
                    assert alpha == (255 if y in marks else 0)
    if parts == 1:
        assert len(result['transition_marks']) == 2
        normal = [p for p in result['placements'] if p['cut_zone'] == '常规区']
        assert result['transition_marks'][0]['y'] == max(p['y_px']+p['height_px'] for p in normal)+3


def test_independent_validation_rejects_wrong_shift_and_colliding_line(tmp_path):
    paths = sources(tmp_path)
    settings = LayoutSettings(dpi=25.4, margin_mm=0, cutter_mode='dual',
        cutter_auto_knife=True, cutter_rotation_zone=True, number_images=False,
        rotation_marker_shift_mm=2, transition_lines=True)
    planned, _, width, _, _ = plan_layout(paths, settings, None)
    corrupt = [(path, replace(p, color_block_x_px=0) if p.cut_zone == '旋转区' else p) for path, p in planned]
    with pytest.raises(ValueError, match='色块未对齐'):
        validate_cut_corridor(corrupt, settings, width)
    line = transition_rects(planned, settings, width)[-1]
    path, p = planned[-1]
    colliding = planned[:-1]+[(path, replace(p, number_y_px=line['y'], number_width_px=1, number_height_px=1))]
    with pytest.raises(ValueError, match='重叠'):
        transition_rects(colliding, settings, width)


@pytest.mark.parametrize('sizes, expected', [
    (['S', 'M', 'L', 'XL'], 'S-XL'), (['S', 'L', 'XL'], 'S+L-XL'),
    (['XXL', '3XL', '4XL', '5XL'], '2XL-5XL'), (['M', 'M'], 'M'),
    (['38', '40', '42'], '38+40+42'),
    (['XL', 'S', 'M', 'L'], 'S+M+L+XL'), (['S', 'M', 'S'], 'S+M'),
])
def test_size_range_does_not_invent_absent_sizes(sizes, expected):
    paths = [Path(f'B{i}-1-T-Black-{size}-NO1-1.png') for i, size in enumerate(sizes)]
    assert size_range_label(paths) == expected


def test_unlimited_budget_keeps_parallel_without_allocating_large_images():
    planned = [(Path('dummy.png'), SimpleNamespace(width_px=3000, height_px=3000))]
    plans = [([], 100000), ([], 100000)]
    settings = LayoutSettings(save_parallelism=2, save_memory_mb=128)
    assert save_concurrency(settings, 7000, plans, planned)[0] == 1
    assert save_concurrency(replace(settings, save_memory_unlimited=True), 7000, plans, planned)[0] == 2
