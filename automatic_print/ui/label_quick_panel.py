from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .setting_preview import SettingPreview


class LabelQuickPanel(QWidget):
    """Main-page editing mirrors the canonical print settings, never a copy."""

    def __init__(self, label, block, parent=None):
        super().__init__(parent)
        self.label = label
        self.text = QLineEdit(label.text_template.text())
        self.text.setPlaceholderText("标签文字：可使用 {编号}、{日期}、{文件名}")
        self.text.textChanged.connect(label.text_template.setText)
        label.text_template.textChanged.connect(self.text.setText)
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(label.font_size.minimum(), label.font_size.maximum())
        self.font_size.setDecimals(1)
        self.font_size.setValue(label.font_size.value())
        self.font_size.valueChanged.connect(label.font_size.setValue)
        label.font_size.valueChanged.connect(self.font_size.setValue)
        self.enabled = self._checkbox("添加标签", label.enabled)
        self.follow_qr = self._checkbox("自动与二维码水平对齐", label.follow_qr)
        self.position = QComboBox()
        for index in range(label.position.count()):
            self.position.addItem(label.position.itemText(index), label.position.itemData(index))
        self.position.setCurrentIndex(label.position.currentIndex())
        self.position.currentIndexChanged.connect(label.position.setCurrentIndex)
        label.position.currentIndexChanged.connect(self.position.setCurrentIndex)
        date_button = QPushButton("添加日期")
        date_button.clicked.connect(self._add_date)
        text_row = QHBoxLayout()
        text_row.addWidget(self.text)
        text_row.addWidget(date_button)
        toggles = QHBoxLayout()
        toggles.addWidget(self.enabled)
        toggles.addWidget(self.follow_qr)
        toggles.addStretch()
        form = QFormLayout()
        form.addRow("标签与文字", text_row)
        form.addRow("文字大小（毫米）", self.font_size)
        form.addRow("位置（未识别二维码时）", self.position)
        form.addRow("", toggles)
        self.label_preview = SettingPreview("label", label._preview_values, self)
        self.block_preview = SettingPreview("block", block._preview_values, self)
        label.settings_changed.connect(self.label_preview.update)
        block.settings_changed.connect(self.block_preview.update)
        previews = QHBoxLayout()
        for title, preview in (
            ("标签实时预览", self.label_preview),
            ("剪膜机色块实时预览", self.block_preview),
        ):
            group = QGroupBox(title)
            QVBoxLayout(group).addWidget(preview)
            previews.addWidget(group, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addLayout(previews)

    def _add_date(self):
        if "{日期}" not in self.text.text():
            self.text.setText(self.text.text().rstrip() + "－{日期}")

    @staticmethod
    def _checkbox(text, source):
        checkbox = QCheckBox(text)
        checkbox.setChecked(source.isChecked())
        checkbox.toggled.connect(source.setChecked)
        source.toggled.connect(checkbox.setChecked)
        return checkbox
