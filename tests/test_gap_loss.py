from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.planning.zones.gap_loss import compare_gap_loss, gap_loss_text


def test_gap_loss_uses_source_paths_same_policy_and_full_film_area(monkeypatch):
    from automatic_print.layout_engine.planning.base import planner
    seen = []
    def plan(paths, settings, progress):
        assert str(paths[0]) == '/tmp/original.png'
        assert settings.membrane_gap_mm == 0
        assert not settings.developer_gap_loss and not settings.compare_film_sizes
        from pathlib import Path
        assert settings.manual_rotations == ((str(Path('/tmp/original.png').resolve()),90),)
        assert settings.sequence_numbers == ((str(Path('/tmp/original.png').resolve()),1),)
        progress('批次刀位已确定',100,25.4,'参考刀位')
        return [], {}, 580, 1000, 1000
    monkeypatch.setattr(planner, 'plan_layout', plan)
    settings = LayoutSettings(dpi=25.4,media_width_mm=580,developer_gap_loss=True,
        manual_rotations=(('/tmp/prepared.png',90),), sequence_numbers=(('/tmp/prepared.png',1),))
    rows = [dict(source='/tmp/original.png',prepared='/tmp/prepared.png',added_px=40)]
    result = compare_gap_loss(rows,settings,1.1,lambda *args:seen.append(args))
    assert abs(result['extra_m']-.1)<1e-10
    assert abs(result['extra_area_m2']-.06)<1e-10
    assert seen[0][0] != '批次刀位已确定'
    assert '增量 +0.100 米' in gap_loss_text(result)


def test_no_added_gap_has_zero_cost_and_no_replan(monkeypatch):
    from automatic_print.layout_engine.planning.base import planner
    monkeypatch.setattr(planner,'plan_layout',lambda *a: (_ for _ in ()).throw(AssertionError()))
    assert compare_gap_loss([],LayoutSettings(),2)['extra_m'] == 0


def test_reference_failure_is_nonblocking(monkeypatch):
    from automatic_print.layout_engine.planning.base import planner
    def fail(*args):
        raise ValueError('参考宽度不足')
    monkeypatch.setattr(planner,'plan_layout',fail)
    result=compare_gap_loss([dict(source='/tmp/a.png',added_px=40)],LayoutSettings(),2)
    text=gap_loss_text(result)
    assert '参考宽度不足' in text
    assert '不影响当前排版' in text
    assert '禁止输出' not in text


def test_actual_preview_compares_added_rows_without_output(tmp_path, monkeypatch):
    from test_header_gap import sample
    from automatic_print.layout_engine.labeling.base import header_gap
    from automatic_print.layout_engine import generate_layout
    monkeypatch.setattr(header_gap,'cache_root',lambda:tmp_path/'cache')
    path=sample(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    settings=LayoutSettings(dpi=25.4,media_width_mm=580,cutter_mode='single',
        cutter_left_marker_external=True,preserve_header_gap=True,
        membrane_gap_mm=40,developer_gap_loss=True,allow_rotation=False)
    result=generate_layout([path],tmp_path/'out',settings,preview_only=True)
    data=result['analysis']['gap_loss']
    assert data['changed_images']==1
    assert abs(data['extra_m']-.032)<1e-8
    assert not (tmp_path/'out').exists()
