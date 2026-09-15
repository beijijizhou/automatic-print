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
def test_width_outlier_does_not_force_pairable_runs_to_single_rows(tmp_path, engine):
    paths = _sources(tmp_path)
    result = generate_layout(paths, tmp_path/'out', LayoutSettings(
        dpi=25.4, media_width_mm=580, margin_mm=0, spacing_mm=8,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=True,
        cutter_left_marker_external=True, number_images=False, png_engine=engine,
    ))
    placements = result['placements']
    rows = {}
    for placement in placements:
        rows.setdefault((placement['cut_zone'], placement['row_y_px']), []).append(placement)
    assert sum(len(row) == 2 for row in rows.values()) == 2
    assert [placement['source'] for placement in placements] == [path.name for path in paths]
    assert len({placement['cut_zone'] for placement in placements}) == 3
    assert result['analysis']['rotation_comparison']['selected_strategy'] == '连续刀位分区双排'
    assert result['width_px'] == max(
        placement['x_px']+placement['width_px'] for placement in placements
    )
    assert result['width_px'] < 580
    assert result['cut_corridor']['pixel_verified']


def test_batch_end_block_is_the_only_reason_to_restore_full_film_width(tmp_path):
    paths = _sources(tmp_path)
    base = LayoutSettings(dpi=25.4, media_width_mm=580, margin_mm=0,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=True,
        cutter_left_marker_external=True, number_images=False)
    cropped = generate_layout(paths, tmp_path/'cropped', base)
    full = generate_layout(paths, tmp_path/'full',
                           LayoutSettings(**(base.__dict__ | {'batch_end_block': True})))
    assert cropped['width_px'] < 580
    assert full['width_px'] == 580
