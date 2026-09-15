from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine import rotation_zones
from automatic_print.layout_engine.single_rotation import eligible_tail
from automatic_print.layout_engine.planner import plan_layout
from test_linear_batch_summary import data


def config(**extra):
    return LayoutSettings(dpi=25.4, media_width_mm=600, margin_mm=3,
        cutter_mode='dual', cutter_auto_knife=True, number_images=False,
        cutter_rotation_zone=True, **extra)


def sources(root):
    paths = []
    for i in range(6):
        size, width, height = ('S', 100, 300) if i < 2 else ('M', 150, 200) if i < 4 else ('L', 340, 500)
        for side in (1, 2):
            path = root/f'B{i}-1-T-Black-{size}-NO1-{side}.png'
            Image.new('RGBA', (width, height), 'blue').save(path, dpi=(25.4, 25.4))
            paths.append(path)
    return paths


def test_thousand_double_row_images_have_no_rotation_candidates():
    _, planned = data(1000)
    assert eligible_tail([p for p, _ in planned], (planned, {}, 580, 50000, 50000)) == []


def test_single_policy_never_calls_general_zone_search_and_rotates_only_tail(tmp_path, monkeypatch):
    paths = sources(tmp_path)
    monkeypatch.setattr(rotation_zones, 'select_zones',
                        lambda *a, **kw: pytest.fail('Single batch used full knife/rotation DP'))
    normal = plan_layout(paths, replace(config(), cutter_rotation_zone=False), None)
    result = plan_layout(paths, config(), None)
    assert result[3] < normal[3]
    assert [p for p, v in result[0] if v.rotation_degrees] == paths[-4:]


def test_pairable_slender_double_stays_normal_even_if_rotation_could_be_shorter(tmp_path, monkeypatch):
    paths = sources(tmp_path)[:4]
    monkeypatch.setattr(rotation_zones, 'rotation_items', lambda selected, *a, **kw:
                        ({}, {}) if not selected else pytest.fail('Measured protected double row'))
    normal = plan_layout(paths, replace(config(), cutter_rotation_zone=False), None)
    assert plan_layout(paths, config(), None) == normal


def test_one_paired_row_protects_whole_size_block_and_size_order():
    _, planned = data(8)
    # Unpaired small-size rows cannot migrate past a protected later-size block.
    changed = []
    for i, (path, p) in enumerate(planned):
        size = 'S' if i < 4 else 'M'
        path = path.with_name(path.name.replace('-M-', f'-{size}-'))
        changed.append((path, replace(p, y_px=i*100 if i < 4 else p.y_px)))
    assert eligible_tail([p for p, _ in changed], (changed, {}, 580, 800, 800)) == []


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('parts', [1, 3])
def test_whole_batch_pixel_safety_and_complete_faces(tmp_path, engine, parts):
    paths = sources(tmp_path)
    result = generate_layout(paths, tmp_path/'out', config(png_engine=engine, output_parts=parts,
                             transition_lines=True, save_memory_unlimited=True))
    seen = []
    for part in result.get('parts', [result]):
        assert part['order_check']['single_size_verified']
        for zone in part['cut_corridor'].get('zones', [part['cut_corridor']]):
            assert zone['pixel_verified']
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                path = tmp_path/p['source']
                seen.append(path)
                with Image.open(path) as source:
                    original = np.asarray(source.rotate(p['rotation_degrees'], expand=True))
                actual = np.asarray(output.crop((p['x_px'], p['y_px'],
                    p['x_px']+p['width_px'], p['y_px']+p['height_px'])))
                assert np.array_equal(actual, original)
    assert set(seen) == set(paths) and len(seen) == 12
