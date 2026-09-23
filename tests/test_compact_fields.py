import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings, QPoint
from PySide6.QtWidgets import QApplication

from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.workbench.overview import label_controls

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
    assert panel.order_side_checkbox.isHidden()
    assert not panel.order_side_checkbox.isChecked()
    assert panel.order_side_action.text() == '整单归侧双排（仅本次任务）'
    assert panel.order_side_action.isCheckable()
    panel.order_side_action.setChecked(True)
    settings = window._layout_settings()
    assert settings.order_side_shared_knife and settings.strict_fixed_knife
    assert not settings.cutter_auto_knife and settings.output_parts == 1
    panel.order_side_action.setChecked(False)
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


def test_machine_identity_only_changes_after_explicit_combo_activation(tmp_path, monkeypatch):
    saved = []
    monkeypatch.setattr(label_controls, "persist_machine_number", saved.append)
    prefs = QSettings(str(tmp_path / "machine.ini"), QSettings.IniFormat)
    prefs.setValue("layout/machine_number", "M11")
    window = MainWindow(prefs)
    OWNERS.append(window)
    window.startup_update_timer.stop()
    panel = window.automation_home.label_quick_panel

    assert saved == []
    index = panel.machine.findData("M2")
    panel.machine.setCurrentIndex(index)
    assert saved == []
    panel.machine.activated.emit(index)
    assert saved == ["M2"]
    window.close()
