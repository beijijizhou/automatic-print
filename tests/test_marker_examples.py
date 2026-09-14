import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace
from time import monotonic
import pytest
from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.ui.marker_example_data import build_examples
from automatic_print.ui.main_window import MainWindow
from test_parallel_film_geometry import settings

APP = QApplication.instance() or QApplication([])


def sources(root):
    paths = []
    for side in ('left', 'right'):
        path = root/f'B{side}-1-T-Black-M-NO1-1.png'
        image = Image.new('RGBA', (270, 300))
        x = 0 if side == 'left' else 160
        image.paste('white', (x, 0, x+110, 45))
        image.paste('blue', (50, 90, 220, 270))
        image.save(path, dpi=(25.4, 25.4))
        paths.append(path)
    return paths


def wait_for(predicate):
    until = monotonic()+15
    while not predicate() and monotonic() < until:
        APP.processEvents()
    assert predicate()


def test_four_cases_use_production_geometry_and_never_modify_sources(tmp_path):
    paths = sources(tmp_path)
    original = [p.read_bytes() for p in paths]
    rows = build_examples(paths, settings())
    assert len(rows) == 4
    assert all(r['production'] for r in rows)
    for row in rows:
        item = row['item']
        assert item.rotation_degrees == row['degrees']
        assert item.block_rx == 0
        assert len(row['pixels']) == row['size'][0]*row['size'][1]*4
        if row['degrees']:
            assert item.block_ry == item.image_ry
            assert item.label_ry-item.image_ry >= row['region'].bottom*item.height
    assert [p.read_bytes() for p in paths] == original
    assert set(tmp_path.iterdir()) == set(paths)


def test_missing_side_is_explicit_diagram_not_mirrored_production(tmp_path):
    paths = sources(tmp_path)
    rows = build_examples(paths[:1], settings())
    assert [r['production'] for r in rows] == [True, False, True, False]
    assert all(not r['source'] for r in rows if not r['production'])


def test_main_page_examples_start_after_show_and_refresh_on_parameters(tmp_path, monkeypatch):
    window = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    window.startup_update_timer.stop()
    examples = window.automation_home.label_quick_panel.marker_examples
    assert examples.worker is None
    assert window.automation_home.label_quick_panel.preview_tabs.currentIndex() == 1
    window.show()
    wait_for(lambda: len(examples.results) == 4 and examples.worker is None)
    assert examples.isVisible()
    assert all(not r['production'] for r in examples.results)
    examples.grab().save(str(tmp_path/'four-case-diagram.png'))
    paths = sources(tmp_path)
    examples.use_batch({'planned': [(p, None) for p in paths]})
    wait_for(lambda: all(r['production'] for r in examples.results) and examples.worker is None)
    old = examples.results[0]['item'].block_width
    window.color_block_settings.width.setValue(12)
    wait_for(lambda: examples.results[0]['item'].block_width != old and examples.worker is None)
    assert all('当前批次生产图' in caption.text() for _, caption in examples.cards)
    snapshot = examples.results
    examples.enlarge(2)
    assert examples.detail_dialog.isVisible()
    assert examples.results is snapshot
    examples.detail_dialog.close()
    window.grab().save(str(tmp_path/'four-case-main.png'))
    examples.timer.stop()
    window.preference_autosave.timer.stop()
    window.automation_home.label_quick_panel.preview.stop_loading()
    window.hide()
