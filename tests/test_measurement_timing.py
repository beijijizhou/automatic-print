import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from automatic_print.layout_engine import measurement_timing as timing
from automatic_print.layout_engine.measurement_session import measurement_session
from automatic_print.layout_engine import planner
from test_persistent_plan_cache import config
from test_parallel_film_geometry import qr_sources


def test_nested_steps_are_exclusive_and_errors_still_record(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(timing, 'perf_counter', lambda: now[0])
    with measurement_session() as session:
        with timing.substep('外层'):
            now[0] = 2
            with timing.substep('解压'):
                now[0] = 5
            now[0] = 8
        try:
            with timing.substep('失败步骤'):
                now[0] = 9
                raise ValueError('expected')
        except ValueError:
            pass
        rows = {r['name']: r for r in session.timing.snapshot()['steps']}
    assert rows['外层']['seconds'] == 5
    assert rows['解压']['seconds'] == 3
    assert rows['失败步骤']['seconds'] == 1
    assert timing.STACK.get() == ()


def test_cold_measurements_report_substeps_and_warm_cache_reports_zero(tmp_path):
    paths, reports = qr_sources(tmp_path), []
    planner.plan_layout(paths, config(), None, reports.append)
    data = reports[-1]['measurement_timings']
    rows = {r['name']: r for r in data['steps']}
    # Cold film preparation also locates cards before per-item decoded-source scope.
    assert rows['源图片像素读取与解压']['calls'] == 2*len(paths)
    for name in ('膜标签卡片定位', '平台文字测量', '普通标签文字测量',
                 '平台透明空位搜索', '尺寸与DPI文件信息读取'):
        assert rows[name]['calls'] > 0
        assert rows[name]['seconds'] >= 0
    assert '线程累计' in timing.measurement_text(data)
    reports.clear()
    planner.plan_layout(paths, config(), None, reports.append)
    cached = reports[-1]['measurement_timings']
    assert cached['cache_hit']
    assert all(r['seconds'] == r['calls'] == 0 for r in cached['steps'])
    assert cached['cached_original_steps'] == data['steps']


def test_measurement_text_appears_in_main_data_and_output_report(tmp_path):
    from PySide6.QtWidgets import QApplication
    from automatic_print.ui.batch_summary import BatchSummaryPanel
    from automatic_print.layout_engine.output_sizes import cutting_report
    app = QApplication.instance() or QApplication([])
    paths, reports = qr_sources(tmp_path), []
    planner.plan_layout(paths, config(), None, reports.append)
    panel = BatchSummaryPanel()
    panel.start(tmp_path)
    panel.show_analysis(reports[-1])
    assert '膜标签卡片定位' in panel.measurement.text()
    report = cutting_report({'analysis': reports[-1], 'parts': [],
        'filename': 'test.png', 'placements': [], 'output_dpi': 25.4})
    assert '源图片像素读取与解压' in report
    panel.start(tmp_path/'next')
    assert not panel.measurement.text()
    panel.close()
