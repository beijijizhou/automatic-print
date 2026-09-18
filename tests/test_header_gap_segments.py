import numpy as np
import pytest
from PIL import Image

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.labeling.base import header_gap
from test_header_gap import sample


@pytest.mark.parametrize('mode', ['single', 'dual'])
@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_complete_double_orders_segmented_with_safe_corridors(tmp_path, mode, engine):
    paths = [sample(tmp_path/f'B{order}-1-T-Black-M-NO1-{face}.png',
                    side='left' if order % 2 else 'right')
             for order in range(4) for face in (1, 2)]
    settings = LayoutSettings(
        dpi=25.4, membrane_gap_mm=40, cutter_mode=mode,
        cutter_auto_knife=True, cutter_single_row_rotation=True,
        cutter_compare_whole_rotation=True, cutter_left_marker_external=True,
        preserve_header_gap=True, cutter_knife_dots=False,
        png_engine=engine, output_parts=3, save_memory_unlimited=True,
    )
    result = generate_layout(paths, tmp_path/'out', settings)
    assert result['order_check']['orders'] == 4
    assert result['order_check']['double_pairs'] == 4
    assert len(result['header_gap']) == len(paths)
    for part in result['parts']:
        assert len(part['placements']) % 2 == 0
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for placement in part['placements']:
                original = next(path for path in paths
                                if path.name == placement['source'])
                prepared = header_gap.prepare_one(original, settings)[0]
                with Image.open(prepared) as source, source.rotate(
                    placement['rotation_degrees'], expand=True,
                ) as rotated:
                    crop = output.crop((
                        placement['x_px'], placement['y_px'],
                        placement['x_px']+rotated.width,
                        placement['y_px']+rotated.height,
                    ))
                    expected, actual = np.asarray(rotated), np.asarray(crop)
                    opaque = expected[:, :, 3] == 255
                    assert np.array_equal(actual[opaque], expected[opaque])
            if mode == 'dual':
                for zone in part['cut_corridor'].get('zones', [part['cut_corridor']]):
                    alpha = output.crop((
                        zone['safe_left_px'], zone.get('start_y_px', 0),
                        zone['safe_right_px'], zone.get('end_y_px', output.height),
                    )).getchannel('A')
                    assert alpha.getextrema()[1] == 0


def test_segmented_output_prepares_header_gap_once_for_the_whole_batch(
    tmp_path, monkeypatch,
):
    paths = [sample(tmp_path/f'B{index}-1-T-Black-M-NO1-1.png')
             for index in range(4)]
    calls = []
    original = header_gap.prepare_paths
    def counted(*args, **kwargs):
        calls.append(tuple(args[0]))
        return original(*args, **kwargs)
    monkeypatch.setattr(header_gap, 'prepare_paths', counted)
    result = generate_layout(paths, tmp_path/'out', LayoutSettings(
        dpi=25.4, media_width_mm=580, membrane_gap_mm=40,
        cutter_mode='dual', output_parts=2, save_parallelism=1,
        number_images=False, png_engine='libvips',
    ))
    assert calls == [tuple(paths)]
    assert len(result['header_gap']) == len(paths)
