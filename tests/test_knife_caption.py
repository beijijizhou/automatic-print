from types import SimpleNamespace
from automatic_print.ui.knife_caption import knife_caption


def planned(*values):
    return [(None, SimpleNamespace(cut_zone=name, cut_knife_x_px=knife))
            for name, knife in values]


def test_single_and_rotated_zones_have_no_second_knife():
    text = knife_caption(planned(('单排', None), ('旋转区', None)), 150)
    assert text == '单排：单排，无内部刀位 · 旋转区：单排，无内部刀位'


def test_mixed_zones_keep_actual_coordinates_and_zero():
    text = knife_caption(planned(('常规区', 150), ('旋转区', None), ('左侧', 0)), 150, ' / ')
    assert text == '常规区刀位 25.4 毫米 / 旋转区：单排，无内部刀位 / 左侧刀位 0.0 毫米'


def test_empty_and_invalid_values_do_not_invent_a_knife():
    assert knife_caption(planned(('', None)), 150) == ''
    assert knife_caption(planned(('常规区', 'unknown')), 150) == '常规区：刀位数据异常'


def test_generation_preview_handles_single_row_payload(monkeypatch):
    from automatic_print.ui import generation_preview as module
    monkeypatch.setattr(module, 'install_snapshot', lambda *a, **k: None)
    preview = SimpleNamespace(overview=True, planned=[], update=lambda: None)
    owner = SimpleNamespace(preview=preview, payload={
        'planned': planned(('单排区', None)), 'labels': {},
        'settings': SimpleNamespace(dpi=150, cutter_knife_mm=300)})
    module.GenerationPreviewController.show_pair(owner, 0)
    assert '单排，无内部刀位' in preview.detail


def test_async_preview_handles_single_row_payload(monkeypatch):
    from automatic_print.ui import preview_loader as module
    monkeypatch.setattr(module, 'install_snapshot', lambda *a, **k: None)
    emitted = []
    preview = SimpleNamespace(overview=True, plan_loaded=SimpleNamespace(emit=emitted.append))
    owner = SimpleNamespace(token=1, closed=False, preview=preview,
        launch=lambda: None, status=lambda text: None)
    payload = {'planned': planned(('单排区', None)), 'labels': {},
        'settings': SimpleNamespace(dpi=150), 'warning': '', 'overflow': [], 'saved_meters': 0}
    module.PreviewLoader.finished(owner, 1, payload, '')
    assert emitted == [payload]
    assert '单排，无内部刀位' in preview.detail
