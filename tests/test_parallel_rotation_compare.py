import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from threading import Barrier, get_ident
from dataclasses import replace
from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine import rotation_compare
from automatic_print.layout_engine.cut_validation import corridor_checks
from automatic_print.layout_engine.planner import plan_layout


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('parts', [1, 2])
def test_real_parallel_complete_orders_and_true_normal_baseline(tmp_path, monkeypatch, engine, parts):
    paths = []
    for order, pieces, width, height in [('B1', 2, 100, 300), ('B2', 1, 200, 150)]:
        for piece in range(1, pieces+1):
            for side in (1, 2):
                path = tmp_path/f'{order}-1-T-Black-M-NO{piece}-{side}.png'
                Image.new('RGBA', (width, height), 'blue').save(path, dpi=(25.4, 25.4))
                paths.append(path)
    settings = LayoutSettings(dpi=25.4, media_width_mm=600, margin_mm=0,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=True,
        transition_lines=True, output_parts=parts, png_engine=engine,
        save_memory_unlimited=True)
    baseline = plan_layout(paths, replace(settings, cutter_rotation_zone=False,
                                         cutter_tail_rotation=False), None)
    barrier, threads = Barrier(2), set()
    def concurrent(fn):
        def run(*args, **kwargs):
            threads.add(get_ident())
            barrier.wait(timeout=5)
            return fn(*args, **kwargs)
        return run
    monkeypatch.setattr(rotation_compare, 'plan_cutter_layout', concurrent(rotation_compare.plan_cutter_layout))
    monkeypatch.setattr(rotation_compare, 'plan_rotation_zones', concurrent(rotation_compare.plan_rotation_zones))
    previews = []
    result = generate_layout(paths, tmp_path/'out', settings, plan_ready=previews.append)
    assert len(threads) == 2
    report = previews[0]['analysis']['rotation_comparison']
    assert report['parallelism'] == 2
    assert report['normal_m'] == pytest.approx(baseline[3]/1000)
    assert report['saved_m'] == pytest.approx(report['normal_m']-report['rotation_m'])
    assert report['rotation_m'] == pytest.approx(previews[0]['canvas'][1]/1000)
    assert previews[0]['order_check']
    for part in result.get('parts', [result]):
        assert part['order_check']
        with Image.open(tmp_path/'out'/part['filename']) as output:
            assert all(zone['pixel_verified'] for zone in
                       part['cut_corridor'].get('zones', [part['cut_corridor']]))
            for zone in corridor_checks(part['cut_corridor']):
                stripe = output.crop((zone['safe_left_px'], zone.get('start_y_px', 0),
                                      zone['safe_right_px'], zone.get('end_y_px', output.height)))
                # Printed exact end notices may occupy the otherwise clear corridor.
                for line in part['transition_marks']:
                    if zone.get('start_y_px', 0) <= line['y'] < zone.get('end_y_px', output.height):
                        stripe.paste(0, (0, line['y']-zone.get('start_y_px', 0), stripe.width,
                                         line['y']-zone.get('start_y_px', 0)+line['height']))
                assert stripe.getchannel('A').getextrema()[1] == 0


def test_rotation_switch_is_clickable_from_fast_mode(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from automatic_print.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow(QSettings(str(tmp_path/'settings.ini'), QSettings.IniFormat))
    window.startup_update_timer.stop()
    assert window.cutter_settings.quick_mode.isChecked()
    assert window.cutter_settings.rotation_zone.isEnabled()
    window.cutter_settings.rotation_zone.click()
    assert not window.cutter_settings.quick_mode.isChecked()
    assert window._layout_settings().cutter_rotation_zone
    window.close()
    window.deleteLater()
