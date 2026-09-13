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
