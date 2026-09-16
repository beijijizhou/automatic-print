import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PIL import Image
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.previews.runtime.snapshot import install_snapshot

APP = QApplication.instance() or QApplication([])
OWNERS = []


def test_zoom_expansion_reuses_real_snapshot_and_restores(tmp_path):
    paths = []
    for index in range(8):
        path = tmp_path/f'B{index}-1-T-Black-M-NO1-1.png'
        Image.new('RGBA', (180, 250), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    settings = LayoutSettings(dpi=25.4, media_width_mm=580,
        cutter_mode='dual', cutter_auto_knife=True, number_images=False)
    planned, labels, _, _, _ = plan_layout(paths, settings, None)
    window = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    OWNERS.append(window)
    window.startup_update_timer.stop()
    panel = window.automation_home.label_quick_panel
    panel.preview_tabs.setCurrentIndex(0)
    preview = panel.preview
    preview.overview = True
    install_snapshot(preview, planned, labels, settings)
    window.resize(1300, 1000)
    window.show()
    APP.processEvents()
    controls = panel.preview_viewport
    scale = controls.scale()
    snapshot = preview.planned
    controls.zoom.setValue(300)
    APP.processEvents()
    assert controls.scale() == pytest.approx(scale*3)
    assert panel.preview_scroll.horizontalScrollBar().maximum() > 0
    assert preview.planned is snapshot
    assert not preview.refresh_timer.isActive()
    controls.toggle_expanded()
    APP.processEvents()
    assert controls.dialog.isVisible()
    assert controls.scroll.maximumHeight() == 16777215
    assert preview.planned is snapshot
    assert not preview.refresh_timer.isActive()
    controls.dialog.grab().save(str(tmp_path/'expanded-preview.png'))
    print('预览截图：'+str(tmp_path/'expanded-preview.png'))
    controls.toggle_expanded()
    APP.processEvents()
    assert controls.dialog is None
    assert controls.parentWidget().layout().indexOf(controls) >= 0
    controls.zoom.setValue(100)
    APP.processEvents()
    assert panel.preview_scroll.horizontalScrollBar().maximum() == 0
    assert preview.planned is snapshot
    window.close()


def test_zoom_empty_preview_does_not_read_old_batch(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'empty.ini'), QSettings.IniFormat))
    OWNERS.append(window)
    window.startup_update_timer.stop()
    panel = window.automation_home.label_quick_panel
    panel.preview_viewport.zoom.setValue(200)
    panel.preview_viewport.toggle_expanded()
    APP.processEvents()
    assert panel.preview.loader.active is None
    assert panel.preview.item is None
    panel.preview_viewport.toggle_expanded()
    window.close()
