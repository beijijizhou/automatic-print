from PySide6.QtCore import Qt, Signal
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

from .setting_preview import SettingPreview
from ..layout_engine.labels import compact_label_text


class LabelSettingsDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("标签与文字设置")
        self.setMinimumWidth(520)
        self.enabled = QCheckBox("为每张图片添加编号或文字标签")
        self.enabled.setChecked(True)
        self.follow_qr = QCheckBox(
            "自动识别膜标签二维码，并让文字与二维码水平对齐"
        )
        self.follow_qr.setChecked(True)
        self.machine = QComboBox()
        for index in range(1, 12):
            self.machine.addItem(f"m{index}", f"m{index}")
        self.text_template = QLineEdit("CY 1001Mt26")
        self.text_template.setPlaceholderText(
            "例如：{编号}  或  {编号}－{日期}"
        )
        self.text_template.editingFinished.connect(
            lambda: self.text_template.setText(compact_label_text(self.text_template.text()))
        )
        help_label = QLabel(
            "可复制使用：{编号}、{日期}、{完整文件名}、{文件名}、{机器号}"
        )
        help_label.setWordWrap(True)
        help_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        qr_help = QLabel(
            "识别成功时放在二维码附近，避免另起一行；未识别时自动使用下方设置的位置。"
        )
        qr_help.setWordWrap(True)
        qr_help.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.position = QComboBox()
        for text, value in (
            ("色块下方（固定标记组）", "block_below"),
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
        self.preview = SettingPreview("label", self._preview_values, self)
        self._connect_preview()
        form = QFormLayout()
        for label, widget in (
            ("启用标签", self.enabled),
            ("机器号", self.machine),
            ("二维码自动定位", self.follow_qr),
            ("", qr_help),
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
            "follow_qr": self.follow_qr.isChecked(),
            "text": self.text_template.text(),
            "position": self.position.currentData(),
            "font_size": self.font_size.value(),
            "gap": self.gap.value(),
            "offset_x": self.offset_x.value(),
            "offset_y": self.offset_y.value(),
            "date_format": self.date_format.text(),
            "machine_number": self.machine.currentData(),
        }

    def _connect_preview(self) -> None:
        self.enabled.toggled.connect(self.preview.update)
        self.follow_qr.toggled.connect(self.preview.update)
        self.text_template.textChanged.connect(self.preview.update)
        self.position.currentIndexChanged.connect(self.preview.update)
        self.machine.currentIndexChanged.connect(self.preview.update)
        self.position.currentIndexChanged.connect(self._sync_position)
        self.date_format.textChanged.connect(self.preview.update)
        for box in (self.font_size, self.gap, self.offset_x, self.offset_y):
            box.valueChanged.connect(self.preview.update)
        signals = [
            self.enabled.toggled, self.follow_qr.toggled,
            self.text_template.textChanged, self.position.currentIndexChanged,
            self.date_format.textChanged,
            self.machine.currentIndexChanged,
        ] + [box.valueChanged for box in (
            self.font_size, self.gap, self.offset_x, self.offset_y
        )]
        for signal in signals:
            signal.connect(lambda *_args: self.settings_changed.emit())
        self._sync_position()

    def _sync_position(self, *_args):
        below = self.position.currentData() == "block_below"
        self.follow_qr.setEnabled(not below)
        if below:
            self.follow_qr.setChecked(False)

    @staticmethod
    def _box(value, minimum, maximum) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(1)
        box.setValue(value)
        return box
