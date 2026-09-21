from dataclasses import replace

import pytest

from automatic_print.layout_engine import generate_layout
from automatic_print.ui.previews.markers.data import build_examples
from test_marker_examples import settings, sources


def test_annotation_is_preview_only_and_keeps_raw_pixels(tmp_path):
    from PySide6.QtGui import QImage
    from automatic_print.ui.previews.markers.annotations import annotated_example
    config = replace(
        settings(), cutter_left_marker_external=True,
        cutter_left_marker_lift_mm=1.5,
    )
    data = build_examples(sources(tmp_path), config)[0]
    original = data['pixels']
    raw = QImage(original, *data['size'], QImage.Format_RGBA8888).copy()
    output = annotated_example(raw, data, config)
    assert output.width() == raw.width()+135
    assert output.height() == raw.height()+155
    assert data['pixels'] == original
    assert any(output.pixelColor(x, 70).name() == '#c2410c'
               for x in range(output.width()))
    item = data['item']
    scale = min(
        900/item.footprint_width,
        650/(item.footprint_height-min(0, item.block_ry)),
    )
    label_x = round(100+item.label_rx*scale-4)
    label_y = round(100+(item.label_ry-min(0, item.block_ry))*scale-4)
    assert output.pixelColor(label_x, label_y).name() == '#a21caf'


@pytest.mark.parametrize('mode', ['free', 'single', 'dual'])
@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('degrees', [0, 90])
@pytest.mark.parametrize('stack', [False, True])
def test_example_text_offsets_match_actual_output_plan(
        tmp_path, mode, side, degrees, stack):
    paths = sources(tmp_path)
    path = paths[0 if side == 'left' else 1]
    config = replace(
        settings(), cutter_mode=mode, cutter_left_marker_external=True,
        preserve_header_gap=True, label_fit_height=True,
        platform_below_marker=stack,
        manual_rotations=((str(path.resolve()), degrees),),
    )
    row = next(r for r in build_examples(paths, config)
               if r['side'] == side and r['degrees'] == degrees)
    if not row['production']:
        assert row['fallback_reason'] or not path.exists()
        assert not row['source']
        return
    payload = []
    generate_layout(
        [path], tmp_path/'out', config, preview_only=True,
        plan_ready=payload.append,
    )
    placement = payload[0]['planned'][0][1]
    item = row['item']
    assert (placement.number_x_px-placement.color_block_x_px,
            placement.number_y_px-placement.color_block_y_px) == (
                item.label_rx-item.block_rx, item.label_ry-item.block_ry)
    assert (placement.platform_x_px-placement.color_block_x_px,
            placement.platform_y_px-placement.color_block_y_px) == (
                item.platform_rx-item.block_rx, item.platform_ry-item.block_ry)
    assert row['mode'] == mode
