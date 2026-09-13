import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings

from automatic_print.ui.color_block_settings import (
    ColorBlockSettingsDialog,
)
from automatic_print.ui.label_settings import LabelSettingsDialog
from automatic_print.ui.cutter_settings import CutterSettingsPanel
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox


@pytest.fixture(autouse=True)
def isolated_preferences(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "automatic_print.ui.main_window.QSettings",
        lambda *_args: QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
    )


def _app():
    return QApplication.instance() or QApplication([])


def _render(widget):
    widget.resize(600, 230)
    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    widget.render(image)
    return image


def test_label_preview_updates_sample_text_and_renders():
    _app()
    dialog = LabelSettingsDialog()
    dialog.text_template.setText("{编号}－{文件名}")

    assert dialog.preview.sample_text().startswith("12－B9UV77Y")
    assert not _render(dialog.preview).isNull()
    dialog.close()


def test_color_block_preview_uses_editable_values_and_renders():
    _app()
    dialog = ColorBlockSettingsDialog()
    dialog.set_color("#00ff00")
    dialog.width.setValue(15)

    values = dialog.preview.values()
    assert values["color"] == "#00ff00"
    assert values["width"] == 15
    assert not _render(dialog.preview).isNull()
    dialog.close()


def test_film_parent_clears_stale_mode_and_knife_on_first_change(tmp_path):
    _app()
    preferences = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    width, rotation, direction = QDoubleSpinBox(), QCheckBox(), QComboBox()
    width.setRange(0, 1000)
    width.setValue(450)
    panel = CutterSettingsPanel(preferences, width, rotation, direction)
    assert panel.mode.currentData() == "single"
    panel.film.setCurrentIndex(panel.film.findData(600))
    assert width.value() == 600
    assert panel.mode.currentData() == "dual"
    assert panel.knife.value() == 290
    assert not rotation.isEnabled()
    panel.knife.setValue(310)
    panel.film.setCurrentIndex(panel.film.findData(450))
    assert panel.mode.currentData() == "single"
    assert panel.knife.value() == 215
    assert not panel.knife.isEnabled()
    panel.save()
    assert preferences.value("cutter/film_mm", type=int) == 450


def test_home_hides_online_workflows_and_keeps_local_logs():
    from automatic_print.ui.main_window import MainWindow

    _app()
    window = MainWindow()
    home = window.automation_home
    assert window.windowTitle() == "本地排版工作台"
    assert window.cutter_settings.film.currentData() == 600
    assert window.cutter_settings.mode.currentData() == "dual"
    assert window.cutter_settings.knife.value() == 290
    assert home.main_tabs.isTabVisible(0)
    assert not home.main_tabs.isTabVisible(1)
    assert not home.main_tabs.isTabVisible(2)
    assert home.thread is None
    assert home.log.parent() is home.main_tabs.widget(0)
    assert home.local_summary.isHidden()
    assert home.local_table.isHidden()
    assert home.platform.isHidden()
    window.close()


def test_main_label_edits_and_parameter_edits_share_live_preview_state():
    from automatic_print.ui.main_window import MainWindow
    from PySide6.QtTest import QSignalSpy

    _app()
    window = MainWindow()
    panel = window.automation_home.label_quick_panel
    assert panel.font_size.isHidden()
    assert panel.position.isHidden()
    assert panel.detect_region.isHidden()
    assert panel.reference_height.isHidden()
    label, block = window.label_settings, window.color_block_settings
    panel.text.setText("{编号}－测试")
    assert label.text_template.text() == "{编号}－测试"
    assert panel.preview.sample_text() == "1－测试"
    panel.font_size.setValue(15)
    assert label.font_size.value() == 15
    label.text_template.setText("主界面同步")
    assert panel.text.text() == "主界面同步"
    spy = QSignalSpy(block.settings_changed)
    block.set_color("#00ff00")
    assert spy.count() == 1
    assert panel.preview.settings_getter().color_block_color == "#00ff00"
    assert not _render(panel.preview).isNull()
    window.close()


def test_saved_font_is_preserved_and_lowercase_machine_is_normalized(tmp_path):
    from automatic_print.ui.main_window import MainWindow

    _app()
    window = MainWindow()
    window.preferences = QSettings(str(tmp_path / "legacy.ini"), QSettings.Format.IniFormat)
    window.preferences.setValue("label/font_size_mm", 10)
    window.preferences.setValue("layout/machine_number", "m7")
    window.load_layout_preferences()
    assert window.label_settings.font_size.value() == 10
    assert window.label_settings.machine.currentData() == "M7"
    window.preferences.setValue("label/default_font_3_applied", False)
    window.preferences.setValue("label/font_size_mm", 5)
    window.load_layout_preferences()
    assert window.label_settings.font_size.value() == 5
    window.close()


def test_preferences_autosave_and_restore_on_restart(tmp_path):
    from automatic_print.ui.main_window import MainWindow
    from PySide6.QtTest import QTest

    _app()
    settings = QSettings(str(tmp_path / "restart.ini"), QSettings.Format.IniFormat)
    window = MainWindow(preferences=settings)
    cutter, label, block = window.cutter_settings, window.label_settings, window.color_block_settings
    cutter.film.setCurrentIndex(cutter.film.findData(600))
    cutter.mode.setCurrentIndex(cutter.mode.findData("free"))
    cutter.knife.setValue(310)
    cutter.safety.setValue(4)
    window.spacing.setValue(6)
    label.text_template.setText("客户标签 {机器号}")
    label.machine.setCurrentIndex(label.machine.findData("M11"))
    label.font_size.setValue(6.5)
    label.reference_height.setValue(8)
    label.gap.setValue(2)
    label.offset_x.setValue(-2)
    block.set_color("#00ff00")
    block.width.setValue(12)
    block.height.setValue(9)
    window.folder.setText(str(tmp_path))
    window.automation_home.local_test_mode.setChecked(False)
    window.automation_home.local_merge_batches.setChecked(True)
    QTest.qWait(400)
    assert settings.value("label/font_size_mm", type=float) == 6.5
    # Close immediately after another edit: pending saves must be flushed.
    label.date_format.setText("%m-%d")
    window.close()
    restored = MainWindow(preferences=settings)
    assert restored.cutter_settings.film.currentData() == 600
    assert restored.cutter_settings.mode.currentData() == "free"
    assert restored.cutter_settings.knife.value() == 310
    assert restored.cutter_settings.safety.value() == 4
    assert restored.spacing.value() == 6
    assert restored.label_settings.text_template.text() == "客户标签 {机器号}"
    assert restored.label_settings.machine.currentData() == "M11"
    assert restored.label_settings.font_size.value() == 6.5
    assert restored.label_settings.fit_height.isChecked()
    assert restored.label_settings.reference_height.value() == 8
    assert restored.label_settings.gap.value() == 2
    assert restored.label_settings.offset_x.value() == -2
    assert restored.label_settings.date_format.text() == "%m-%d"
    assert restored.color_block_settings.color == "#00ff00"
    assert restored.color_block_settings.width.value() == 12
    assert restored.color_block_settings.height.value() == 9
    assert restored.folder.text() == str(tmp_path)
    assert not restored.automation_home.local_test_mode.isChecked()
    assert restored.automation_home.local_merge_batches.isChecked()
    restored.close()
