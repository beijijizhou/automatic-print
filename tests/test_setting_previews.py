import os

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
    assert panel.knife.value() == 300
    assert not rotation.isEnabled()
    panel.knife.setValue(310)
    panel.film.setCurrentIndex(panel.film.findData(450))
    assert panel.mode.currentData() == "single"
    assert panel.knife.value() == 225
    assert not panel.knife.isEnabled()
    panel.save()
    assert preferences.value("cutter/film_mm", type=int) == 450


def test_home_hides_online_workflows_and_keeps_local_logs():
    from automatic_print.ui.main_window import MainWindow

    _app()
    window = MainWindow()
    home = window.automation_home
    assert window.windowTitle() == "本地排版工作台"
    assert home.main_tabs.isTabVisible(0)
    assert not home.main_tabs.isTabVisible(1)
    assert not home.main_tabs.isTabVisible(2)
    assert home.thread is None
    assert home.log.parent() is home.main_tabs.widget(0)
    window.close()


def test_main_label_edits_and_parameter_edits_share_live_preview_state():
    from automatic_print.ui.main_window import MainWindow
    from PySide6.QtTest import QSignalSpy

    _app()
    window = MainWindow()
    panel = window.automation_home.label_quick_panel
    label, block = window.label_settings, window.color_block_settings
    panel.text.setText("{编号}－测试")
    assert label.text_template.text() == "{编号}－测试"
    assert panel.label_preview.sample_text() == "12－测试"
    panel.font_size.setValue(15)
    assert label.font_size.value() == 15
    label.text_template.setText("主界面同步")
    assert panel.text.text() == "主界面同步"
    spy = QSignalSpy(block.settings_changed)
    block.set_color("#00ff00")
    assert spy.count() == 1
    assert panel.block_preview.values()["color"] == "#00ff00"
    assert not _render(panel.label_preview).isNull()
    assert not _render(panel.block_preview).isNull()
    window.close()
