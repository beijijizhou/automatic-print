import os
from dataclasses import replace
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from automatic_print.layout_engine.measurement import measurement_timing as timing
from automatic_print.layout_engine.measurement.measurement_session import measurement_session
from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.planning.base import planner
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


def test_dimension_timing_counts_physical_read_once_per_batch(tmp_path):
    path = tmp_path/'source.png'
    from PIL import Image
    Image.new('RGBA', (20, 10)).save(path, dpi=(200, 200))
    with measurement_session() as session:
        first = print_dimensions(path, 300)
        second = print_dimensions(path, 150)
        rows = {row['name']: row for row in session.timing.snapshot()['steps']}
    assert first == second
    assert rows['尺寸与DPI文件信息读取']['calls'] == 1


def test_cold_measurements_report_substeps_and_warm_cache_reports_zero(tmp_path):
    paths, reports = qr_sources(tmp_path), []
    planner.plan_layout(paths, config(), None, reports.append)
    data = reports[-1]['measurement_timings']
    rows = {r['name']: r for r in data['steps']}
    # Production libvips reads only the bounded top strip; Pillow remains a fallback.
    decode = rows.get('顶部标签条带读取与解压') or rows.get('源图片像素读取与解压')
    assert decode['calls'] == len(paths)
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


def test_per_image_measurement_cache_survives_batch_geometry_change(tmp_path, monkeypatch):
    paths = qr_sources(tmp_path)[:2]
    initial = replace(config(), compare_film_sizes=False)
    planner.plan_layout(paths, initial, None)
    from automatic_print.layout_engine.intake.preparation import item_factory
    monkeypatch.setattr(
        item_factory, '_make_item',
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError('remeasured source')),
    )
    reports = []
    planner.plan_layout(
        paths, replace(initial, media_width_mm=initial.media_width_mm-10),
        None, reports.append,
    )
    measured = reports[-1]['measurement_timings']
    assert measured['item_cache_hits'] >= len(paths)
    assert measured['item_cache_misses'] == 0


def test_measurement_text_stays_internal_to_diagnostics(tmp_path):
    from PySide6.QtWidgets import QApplication
    from automatic_print.ui.batch_summary import BatchSummaryPanel
    from automatic_print.layout_engine.output.output_sizes import cutting_report
    app = QApplication.instance() or QApplication([])
    paths, reports = qr_sources(tmp_path), []
    planner.plan_layout(paths, config(), None, reports.append)
    panel = BatchSummaryPanel()
    panel.start(tmp_path)
    panel.show_analysis(reports[-1])
    assert not hasattr(panel, 'measurement')
    report = cutting_report({'analysis': reports[-1], 'parts': [],
        'filename': 'test.png', 'placements': [], 'output_dpi': 25.4})
    assert '测量子步骤' not in report and '读取与解压' not in report
    panel.start(tmp_path/'next')
    panel.close()
