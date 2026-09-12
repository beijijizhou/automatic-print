from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .setting_preview import SettingPreview


class ColorBlockSettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("色块设置")
        self.setMinimumWidth(560)
        self.enabled = QCheckBox("为每张图片添加剪膜机识别色块")
        self.enabled.setChecked(True)
        self.color = "#ff0000"
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self.choose_color)
        self._show_color()
        self.width = self._box(10, 1, 100)
        self.height = self._box(10, 1, 100)
        self.position = QComboBox()
        for text, value in (
            ("左侧顶部对齐（默认）", "left_top"),
            ("左侧居中", "left"),
            ("左侧底部对齐", "left_bottom"),
        ):
            self.position.addItem(text, value)
        self.gap = self._box(5, 0, 100)
        self.offset_x = self._box(0, -100, 100)
        self.offset_y = self._box(0, -100, 100)
        note = QLabel(
            "色块始终位于图片左侧并与图片处于同一高度，适配左侧识别器，且不增加材料长度。"
        )
        note.setWordWrap(True)
        self.preview = SettingPreview("block", self._preview_values, self)
        self._connect_preview()
        form = QFormLayout()
        for label, widget in (
            ("启用色块", self.enabled),
            ("色块颜色", self.color_button),
            ("宽度（毫米）", self.width),
            ("高度（毫米）", self.height),
            ("色块位置", self.position),
            ("与图片距离（毫米）", self.gap),
            ("水平微调（毫米）", self.offset_x),
            ("垂直微调（毫米）", self.offset_y),
            ("", note),
        ):
            form.addRow(label, widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview)
        layout.addWidget(buttons)

    def _preview_values(self) -> dict:
        return {
            "enabled": self.enabled.isChecked(),
            "color": self.color,
            "width": self.width.value(),
            "height": self.height.value(),
            "position": self.position.currentData(),
            "gap": self.gap.value(),
            "offset_x": self.offset_x.value(),
            "offset_y": self.offset_y.value(),
        }

    def _connect_preview(self) -> None:
        self.enabled.toggled.connect(self.preview.update)
        self.position.currentIndexChanged.connect(self.preview.update)
        for box in (
            self.width, self.height, self.gap, self.offset_x, self.offset_y
        ):
            box.valueChanged.connect(self.preview.update)

    def choose_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.color), self, "选择色块颜色")
        if color.isValid():
            self.color = color.name()
            self._show_color()

    def set_color(self, value: str) -> None:
        color = QColor(value)
        self.color = color.name() if color.isValid() else "#ff0000"
        self._show_color()

    def _show_color(self) -> None:
        name = "正红色" if self.color.lower() == "#ff0000" else "当前颜色"
        self.color_button.setText(f"{name}  {self.color.upper()}")
        self.color_button.setStyleSheet(
            f"background:{self.color};color:white;font-weight:700;"
            "min-height:30px;"
        )
        if hasattr(self, "preview"):
            self.preview.update()

    @staticmethod
    def _box(value, minimum, maximum) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(1)
        box.setValue(value)
        return box
