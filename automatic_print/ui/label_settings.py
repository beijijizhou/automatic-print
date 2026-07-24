from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)


class LabelSettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("标签与文字设置")
        self.setMinimumWidth(520)
        self.enabled = QCheckBox("为每张图片添加编号或文字标签")
        self.enabled.setChecked(True)
        self.text_template = QLineEdit("{编号}")
        self.text_template.setPlaceholderText(
            "例如：{编号}  或  {编号}－{日期}"
        )
        help_label = QLabel(
            "可复制使用：{编号}、{日期}、{完整文件名}、{文件名}"
        )
        help_label.setWordWrap(True)
        help_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.position = QComboBox()
        for text, value in (
            ("图片下方", "bottom"),
            ("图片上方", "top"),
            ("图片左侧", "left"),
            ("图片右侧", "right"),
            ("左上角（图片外）", "top_left"),
            ("右上角（图片外）", "top_right"),
            ("左下角（图片外）", "bottom_left"),
            ("右下角（图片外）", "bottom_right"),
        ):
            self.position.addItem(text, value)
        self.font_size = self._box(10, 2, 50)
        self.gap = self._box(5, 0, 100)
        self.offset_x = self._box(0, -100, 100)
        self.offset_y = self._box(0, -100, 100)
        self.date_format = QLineEdit("%Y-%m-%d")
        form = QFormLayout()
        for label, widget in (
            ("启用标签", self.enabled),
            ("标签文字", self.text_template),
            ("", help_label),
            ("标签位置", self.position),
            ("文字大小（毫米）", self.font_size),
            ("与图片距离（毫米）", self.gap),
            ("水平微调（毫米）", self.offset_x),
            ("垂直微调（毫米）", self.offset_y),
            ("日期格式", self.date_format),
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

    @staticmethod
    def _box(value, minimum, maximum) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(1)
        box.setValue(value)
        return box
