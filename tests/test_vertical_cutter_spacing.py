from dataclasses import replace

import pytest
from PIL import Image

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.cutter_planner import plan_cutter_layout
from automatic_print.layout_engine.models import mm_to_px


@pytest.mark.parametrize('mode', ['single', 'dual'])
def test_vertical_spacing_changes_row_distance_not_horizontal_knife_geometry(tmp_path, mode):
    paths = []
    for order in ('ORDERA', 'ORDERB'):
        for side in (1, 2):
            path = tmp_path / f'{order}-1-T-Black-M-NO1-{side}.png'
            Image.new('RGBA', (200, 300), 'blue').save(path, dpi=(25.4, 25.4))
            paths.append(path)
    settings = LayoutSettings(
        media_width_mm=600, dpi=25.4, margin_mm=0, spacing_mm=8,
        number_images=False, cutter_mode=mode, cutter_knife_mm=300,
        cutter_auto_knife=False, allow_rotation=False,
    )
    planned, *_ = plan_cutter_layout(paths, settings, None)
    changed, *_ = plan_cutter_layout(paths, replace(settings, spacing_mm=11), None)
    for (path, item), (other_path, other) in zip(planned, changed):
        assert path == other_path
        assert item.x_px == other.x_px
        assert item.color_block_x_px == other.color_block_x_px
    rows = {}
    for _, item in planned:
        rows.setdefault(item.row_y_px, []).append(item)
    ordered = sorted(rows.items())
    for (top, items), (next_top, _) in zip(ordered, ordered[1:]):
        bottom = max(top + item.footprint_height_px for item in items)
        assert next_top - bottom == mm_to_px(8, settings.dpi)
    assert changed[-1][1].y_px > planned[-1][1].y_px
