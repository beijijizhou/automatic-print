import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings, QPoint, Qt
from PySide6.QtWidgets import QApplication

from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
OWNERS = []


def test_one_row_highlight_and_default_comparison_migration(tmp_path):
    prefs = QSettings(str(tmp_path/'fields.ini'), QSettings.IniFormat)
    prefs.setValue('source_location', str(tmp_path/'BATCH123'))
    prefs.setValue('cutter/compare_films', False)  # Old default must migrate once.
    window = MainWindow(prefs)
    window.department_selector.setCurrentIndex(window.department_selector.findData('dtf'))
    OWNERS.append(window)
    window.startup_update_timer.stop()
    window.show()
    APP.processEvents()
    panel = window.automation_home.label_quick_panel
    controls = (panel.text, panel.platform, panel.platform_font_height, panel.machine)
    assert max(c.mapTo(panel, QPoint()).y() for c in controls)-min(
        c.mapTo(panel, QPoint()).y() for c in controls) < 10
    assert all(c.isVisible() for c in controls)
    assert panel.order_side_checkbox.isVisible()
    assert not panel.order_side_checkbox.isChecked()
    assert '隆丰共刀' in panel.order_side_label.text()
    assert panel.order_side_label.textInteractionFlags() & Qt.TextSelectableByMouse
    assert 'BATCH123' in panel.selected_source.text()
    assert '#dbeafe' in panel.selected_source.styleSheet()
    assert not panel.preview.loader.active and not panel.preview.batch_payload
    assert window._layout_settings().compare_film_sizes
    assert panel.summary.film_table.rowCount() == 4
    viewport = window.automation_home.workbench_scroll.viewport()
    window.automation_home.workbench_scroll.ensureWidgetVisible(panel.summary.film_table)
    APP.processEvents()
    assert panel.summary.film_table.mapTo(viewport, QPoint(0, panel.summary.film_table.height())).y() < viewport.height()
    window.cutter_settings.compare_films.setChecked(False)
    window.close()
    fresh = MainWindow(prefs)
    OWNERS.append(fresh)
    fresh.startup_update_timer.stop()
    assert not fresh._layout_settings().compare_film_sizes  # Later explicit changes persist.
    fresh.close()
