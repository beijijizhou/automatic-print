from PIL import Image

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.planning.base.planner import plan_layout


def test_free_layout_selects_whole_batch_rotation_when_shorter(tmp_path):
    paths = []
    for index in range(4):
        path = tmp_path / f'B{index}-1-T-Black-XL-NO1-1.png'
        Image.new('RGBA', (300, 100), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    progress = []
    planned, _labels, _width, height, _baseline = plan_layout(
        paths,
        LayoutSettings(
            dpi=25.4,
            media_width_mm=580,
            margin_mm=0,
            spacing_mm=8,
            cutter_mode='free',
            allow_rotation=True,
            number_images=False,
            color_block_enabled=False,
        ),
        lambda *values: progress.append(values),
    )

    assert height == 300
    assert {placement.rotation_degrees for _path, placement in planned} == {90}
    assert any(stage == '排版方案已确定' and '整批旋转' in detail
               for stage, _current, _total, detail in progress)
