import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings, QPoint
from PySide6.QtWidgets import QApplication

from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.workbench.overview import label_controls
from automatic_print.automation.api.machine_status import identity

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


def test_label_machine_selection_does_not_change_registered_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    identity.bind_machine_slot("M11")
    prefs = QSettings(str(tmp_path / "machine.ini"), QSettings.IniFormat)
    prefs.setValue("layout/machine_number", "M11")
    window = MainWindow(prefs)
    OWNERS.append(window)
    window.startup_update_timer.stop()
    panel = window.automation_home.label_quick_panel

    index = panel.machine.findData("M2")
    panel.machine.setCurrentIndex(index)
    panel.machine.activated.emit(index)
    assert identity.machine_name() == "M11"
    window.close()


def test_layout_autosave_cannot_replace_bound_machine_slot(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    identity.bind_machine_slot("M11")
    prefs = QSettings(str(tmp_path / "machine.ini"), QSettings.IniFormat)
    prefs.setValue("layout/machine_number", "M1")
    window = MainWindow(prefs)
    OWNERS.append(window)
    window.startup_update_timer.stop()

    window.save_layout_preferences(notify=False)
    identity._write_machine_number(identity.machine_name_file(), "M1")
    identity._write_machine_number(
        identity.identity_file().with_name("machine-binding"), "M1",
    )

    assert identity.machine_name() == "M11"
    assert identity.machine_slot_file().read_text(encoding="utf-8") == "M11"
    window.close()
