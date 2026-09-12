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


class ColorBlockSettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("色块设置")
        self.setMinimumWidth(480)
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
            ("左上角（图片外）", "top_left"),
            ("上方居中", "top"),
            ("右上角（图片外）", "top_right"),
            ("左侧居中", "left"),
            ("右侧居中", "right"),
            ("左下角（图片外）", "bottom_left"),
            ("下方居中", "bottom"),
            ("右下角（图片外）", "bottom_right"),
        ):
            self.position.addItem(text, value)
        self.gap = self._box(5, 0, 100)
        self.offset_x = self._box(0, -100, 100)
        self.offset_y = self._box(0, -100, 100)
        note = QLabel("基础位置位于图片外侧，微调后仍计入排版占用空间。")
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
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

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

    @staticmethod
    def _box(value, minimum, maximum) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(1)
        box.setValue(value)
        return box
