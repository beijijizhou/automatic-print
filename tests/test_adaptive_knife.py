from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout


def _sources(root):
    paths = []
    for index, width in enumerate((250, 250, 350, 250, 250), 1):
        path = root/f'B{index}-1-T-Black-M-NO1-1.png'
        Image.new('RGBA', (width, 100), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    return paths


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_pairable_majority_precedes_one_rotated_leftover_zone(tmp_path, engine):
    paths = _sources(tmp_path)
    result = generate_layout(paths, tmp_path/'out', LayoutSettings(
        dpi=25.4, media_width_mm=580, margin_mm=0, spacing_mm=8,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=True,
        cutter_majority_two_zone=True,
        cutter_left_marker_external=True, number_images=False, png_engine=engine,
    ))
    placements = result['placements']
    rows = {}
    for placement in placements:
        rows.setdefault((placement['cut_zone'], placement['row_y_px']), []).append(placement)
    assert sum(len(row) == 2 for row in rows.values()) == 2
    assert [placement['source'] for placement in placements] == [
        paths[i].name for i in (0, 1, 3, 4, 2)
    ]
    assert {placement['cut_zone'] for placement in placements} == {'并排区', '旋转区'}
    assert sum(placement['rotation_degrees'] != 0 for placement in placements) == 1
    assert result['analysis']['rotation_comparison']['selected_strategy'] == '多数并排区 + 剩余旋转区'
    assert result['width_px'] == max(
        placement['x_px']+placement['width_px'] for placement in placements
    )
    assert result['width_px'] < 580
    assert result['cut_corridor']['pixel_verified']


def test_batch_end_block_is_the_only_reason_to_restore_full_film_width(tmp_path):
    paths = _sources(tmp_path)
    base = LayoutSettings(dpi=25.4, media_width_mm=580, margin_mm=0,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=True,
        cutter_majority_two_zone=True,
        cutter_left_marker_external=True, number_images=False)
    cropped = generate_layout(paths, tmp_path/'cropped', base)
    full = generate_layout(paths, tmp_path/'full',
                           LayoutSettings(**(base.__dict__ | {'batch_end_block': True})))
    assert cropped['width_px'] < 580
    assert full['width_px'] == 580


def test_only_oversized_rotated_leftover_is_scaled(tmp_path, monkeypatch):
    from automatic_print.layout_engine import width_fit
    monkeypatch.setattr(width_fit, 'cache_root', lambda: tmp_path/'cache')
    paths = _sources(tmp_path)[:4]
    oversized = tmp_path/'B9-1-T-Black-M-NO1-1.png'
    Image.new('RGBA', (900, 700), 'red').save(oversized, dpi=(25.4, 25.4))
    paths.append(oversized)
    result = generate_layout(paths, tmp_path/'scaled', LayoutSettings(
        dpi=25.4, media_width_mm=580, margin_mm=0, spacing_mm=8,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=True,
        cutter_majority_two_zone=True,
        cutter_left_marker_external=True, number_images=False, auto_fit_width=True,
    ))
    assert len(result['analysis']['width_adjustments']) == 1
    assert {p['cut_zone'] for p in result['placements']} == {'并排区', '旋转区'}
    scaled = next(p for p in result['placements'] if p['source'] == oversized.name)
    assert scaled['rotation_degrees'] == 90 and scaled['width_px'] < 580


def test_developer_width_cap_forces_s_to_l_pairs_without_enlarging(tmp_path):
    paths = []
    for index, (width, size) in enumerate(((280, 'S'), (250, 'S'),
                                           (285, 'M'), (290, 'L')), 1):
        path = tmp_path/f'B{index}-1-T-Black-{size}-NO1-1.png'
        Image.new('RGBA', (width, 120), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    result = generate_layout(paths, tmp_path/'unused', LayoutSettings(
        dpi=25.4, media_width_mm=580, margin_mm=0, spacing_mm=8,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=True,
        cutter_majority_two_zone=True, force_small_pair_width=True,
        cutter_left_marker_external=True, number_images=False,
    ))
    placements = result['placements']
    rows = {}
    for placement in placements:
        rows.setdefault((placement['cut_zone'], placement['row_y_px']), []).append(placement)
    assert [sorted(p['width_px'] for p in row) for row in rows.values()] == [
        [250, 270], [270, 270]
    ]
    assert all(len(row) == 2 for row in rows.values())
    assert len(result['analysis']['width_adjustments']) == 3
    knives = {p['cut_knife_x_px'] for p in placements}
    assert len(knives) == 1
    assert knives == {result['cut_corridor']['zones'][0]['knife_x_px']}
    right_markers = {p['color_block_x_px'] for p in placements
                     if p['x_px'] > next(iter(knives))}
    assert len(right_markers) == 1
    output = tmp_path/'unused'/result['filename']
    with Image.open(output) as rendered:
        assert rendered.size == (result['width_px'], result['height_px'])
    output.unlink()
