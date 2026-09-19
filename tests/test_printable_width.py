import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
from PIL import Image
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from automatic_print.layout_engine import generate_layout
from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def make_window(tmp_path):
    prefs = QSettings(str(tmp_path/'riin.ini'), QSettings.IniFormat)
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    return window, prefs


def test_physical_film_and_riin_margins_persist_and_update_capacity(tmp_path):
    window, prefs = make_window(tmp_path)
    cutter = window.cutter_settings
    assert window.width.value() == 600
    assert window._layout_settings().media_width_mm == 570
    assert window._layout_settings().fixed_output_width_mm == 570
    assert cutter.printable.left.value() == cutter.printable.right.value() == 15
    assert cutter.knife.value() == 285
    assert window.quick_output_width.value() == 570
    window.quick_output_width.setValue(560)
    assert cutter.printable.left.value() == cutter.printable.right.value() == 20
    assert window._layout_settings().media_width_mm == 560
    cutter.printable.output_width.setValue(570)
    assert window.quick_output_width.value() == 570
    cutter.printable.left.setValue(12)
    cutter.printable.right.setValue(8)
    cutter.film.setCurrentIndex(cutter.film.findData(450))
    assert window.width.value() == 450
    assert window._layout_settings().media_width_mm == 430
    assert window.quick_output_width.value() == 430
    assert cutter.knife.maximum() == 429
    assert cutter.knife.value() == 215
    window.close()
    reopened = MainWindow(prefs)
    WINDOWS.append(reopened)
    reopened.startup_update_timer.stop()
    assert reopened.cutter_settings.printable.left.value() == 12
    assert reopened.cutter_settings.printable.right.value() == 8
    assert reopened._layout_settings().media_width_mm == 430
    assert reopened.quick_output_width.value() == 430
    reopened.close()


def test_invalid_margin_sum_is_rejected(tmp_path):
    window, _prefs = make_window(tmp_path)
    width = window.cutter_settings.printable
    width.left.setValue(300)
    width.right.setValue(300)
    with pytest.raises(ValueError, match='左右预留'):
        window._layout_settings()
    assert '= 0 毫米' in width.description.text()
    window.close()


def test_old_10_mm_defaults_migrate_but_custom_margins_remain(tmp_path):
    prefs = QSettings(str(tmp_path/'migrate.ini'), QSettings.IniFormat)
    prefs.setValue('riin/left_mm', 10)
    prefs.setValue('riin/right_mm', 10)
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    assert window.quick_output_width.value() == 570
    window.close()
    prefs.setValue('riin/left_mm', 12)
    prefs.setValue('riin/right_mm', 8)
    reopened = MainWindow(prefs)
    WINDOWS.append(reopened)
    reopened.startup_update_timer.stop()
    assert reopened.quick_output_width.value() == 580
    assert (reopened.cutter_settings.printable.left.value(),
            reopened.cutter_settings.printable.right.value()) == (12, 8)
    reopened.close()


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_entire_batch_keeps_fixed_canvas_and_pixel_safe_knife(tmp_path, engine):
    window, _prefs = make_window(tmp_path)
    paths = []
    for order in range(6):
        for face in (1, 2):
            path = tmp_path/f'B{order}-1-T-Black-M-NO1-{face}.png'
            Image.new('RGBA', (260, 60), 'blue').save(path, dpi=(25.4, 25.4))
            paths.append(path)
    settings = replace(window._layout_settings(), dpi=25.4, number_images=False,
                       png_engine=engine, cutter_auto_knife=False, margin_mm=0)
    payloads = []
    result = generate_layout(paths, tmp_path/'out', settings, plan_ready=payloads.append)
    assert result['maximum_width_mm'] == 570
    assert result['width_px'] == 570
    assert result['film_width_mm'] == 600
    assert result['width_px'] >= max(
        placement['x_px'] + placement['width_px'] for placement in result['placements'])
    assert result['order_check']['double_pairs'] == 6
    for placement in result['placements']:
        assert placement['x_px']+placement['width_px'] <= 570
    output = tmp_path/'out'/result['filename']
    with Image.open(output) as image:
        assert image.width == result['width_px']
        # Knife safety is fixed at zero: artwork may touch either side of the
        # mathematical boundary, but validation proves it never crosses it.
        for mark in result['transition_marks']:
            assert image.getpixel((285, mark['y'])) == (255, 0, 0, 255)
        assert result['cut_corridor']['pixel_verified']
    controller = window.generation_preview
    controller.start()
    controller.ready(payloads[0])
    assert controller.preview.film_width == 570
    assert '可用宽度 570' in controller.panel.summary.metrics.text()
    controller.end()
    window.close()
