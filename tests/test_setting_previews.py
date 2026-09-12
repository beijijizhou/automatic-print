import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from automatic_print.ui.color_block_settings import (
    ColorBlockSettingsDialog,
)
from automatic_print.ui.label_settings import LabelSettingsDialog


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
