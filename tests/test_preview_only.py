from PIL import Image

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.pipeline import service
from automatic_print.layout_engine.pipeline import render_output
from automatic_print.layout_engine.planning.base.planner import plan_layout
from automatic_print.layout_engine.output.output_sizes import cutting_report


def test_preview_does_not_build_canvas_or_create_output(tmp_path, monkeypatch):
    path = tmp_path / 'ORDER-1-NO1-1.png'
    Image.new('RGBA', (80, 120), 'blue').save(path, dpi=(25.4, 25.4))
    def forbidden(*args, **kwargs):
        raise AssertionError('Preview must not render final canvas')
    monkeypatch.setattr(render_output, 'render_output', forbidden)
    payloads = []
    result = service.generate_layout([path], tmp_path/'absent',
        LayoutSettings(dpi=25.4, number_images=False),
        plan_ready=payloads.append, preview_only=True)
    assert result['preview_only']
    assert result['filename'].endswith('.png')
    assert len(result['placements']) == 1
    assert result['operation_timings']['status'] == '已完成'
    assert result['operation_timings']['total_seconds'] >= 0
    assert '单列 / 自由排版' in cutting_report(result)
    assert len(payloads[0]['planned']) == 1
    assert not (tmp_path/'absent').exists()


def test_normal_double_pair_image_tops_align(tmp_path):
    paths = []
    for side, height in ((1, 120), (2, 200)):
        path = tmp_path/f'ORDER-1-NO1-{side}.png'
        Image.new('RGBA', (100, height), 'blue').save(path, dpi=(25.4,25.4))
        paths.append(path)
    plan = plan_layout(paths, LayoutSettings(dpi=25.4, number_images=False,
        cutter_mode='dual', cutter_rotation_zone=False), None)
    left, right = [p for _, p in plan[0]]
    assert left.y_px == right.y_px
    assert left.x_px != right.x_px
