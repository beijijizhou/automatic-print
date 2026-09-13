from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .production_preview import ProductionPreview
from ..layout_engine.labels import compact_label_text


class LabelQuickPanel(QWidget):
    """Main-page editing mirrors the canonical print settings, never a copy."""

    def __init__(self, label, block, parent=None, window=None):
        super().__init__(parent)
        self.label = label
        self.text = QLineEdit(label.text_template.text())
        self.text.setPlaceholderText("标签文字：可使用 {编号}、{日期}、{文件名}")
        self.text.textChanged.connect(label.text_template.setText)
        label.text_template.textChanged.connect(self.text.setText)
        self.text.editingFinished.connect(
            lambda: self.text.setText(compact_label_text(self.text.text()))
        )
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(label.font_size.minimum(), label.font_size.maximum())
        self.font_size.setDecimals(1)
        self.font_size.setValue(label.font_size.value())
        self.font_size.valueChanged.connect(label.font_size.setValue)
        label.font_size.valueChanged.connect(self.font_size.setValue)
        self.enabled = self._checkbox("添加标签", label.enabled)
        self.follow_qr = self._checkbox("自动与二维码水平对齐", label.follow_qr)
        self.follow_qr.setEnabled(label.follow_qr.isEnabled())
        self.machine = QComboBox()
        for index in range(label.machine.count()):
            self.machine.addItem(label.machine.itemText(index), label.machine.itemData(index))
        self.machine.setCurrentIndex(label.machine.currentIndex())
        self.machine.currentIndexChanged.connect(label.machine.setCurrentIndex)
        label.machine.currentIndexChanged.connect(self.machine.setCurrentIndex)
        label.machine.currentIndexChanged.connect(
            lambda *_args: window.preferences.setValue("layout/machine_number", label.machine.currentData())
        )
        self.position = QComboBox()
        for index in range(label.position.count()):
            self.position.addItem(label.position.itemText(index), label.position.itemData(index))
        self.position.setCurrentIndex(label.position.currentIndex())
        self.position.currentIndexChanged.connect(label.position.setCurrentIndex)
        label.position.currentIndexChanged.connect(self.position.setCurrentIndex)
        self.position.currentIndexChanged.connect(
            lambda *_args: self.follow_qr.setEnabled(label.follow_qr.isEnabled())
        )
        date_button = QPushButton("添加日期")
        date_button.clicked.connect(self._add_date)
        machine_button = QPushButton("添加机器号")
        machine_button.clicked.connect(self._add_machine)
        text_row = QHBoxLayout()
        text_row.addWidget(self.text)
        text_row.addWidget(date_button)
        text_row.addWidget(machine_button)
        toggles = QHBoxLayout()
        toggles.addWidget(self.enabled)
        toggles.addWidget(self.follow_qr)
        toggles.addStretch()
        form = QFormLayout()
        compact_button = QPushButton("紧凑字号（3毫米）")
        compact_button.clicked.connect(lambda: self.font_size.setValue(3))
        font_row = QHBoxLayout()
        font_row.addWidget(self.font_size)
        font_row.addWidget(compact_button)
        form.addRow("标签与文字", text_row)
        form.addRow("当前机器号", self.machine)
        form.addRow("文字大小（毫米）", font_row)
        form.addRow("标签位置", self.position)
        form.addRow("", toggles)
        self.preview = ProductionPreview(window._layout_settings, self)
        label.settings_changed.connect(self.preview.refresh)
        block.settings_changed.connect(self.preview.refresh)
        window.folder.textChanged.connect(self.preview.use_folder)
        window.dpi.valueChanged.connect(self.preview.refresh)
        group = QGroupBox("生产图片样板 · 标签与色块联合预览")
        QVBoxLayout(group).addWidget(self.preview)
        self.preview.use_folder(window.folder.text())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addWidget(group)

    def _add_date(self):
        if "{日期}" not in self.text.text():
            self.text.setText(self.text.text().rstrip() + "－{日期}")

    def _add_machine(self):
        if "{机器号}" not in self.text.text():
            self.text.setText(self.text.text().rstrip() + "－{机器号}")

    @staticmethod
    def _checkbox(text, source):
        checkbox = QCheckBox(text)
        checkbox.setChecked(source.isChecked())
        checkbox.toggled.connect(source.setChecked)
        source.toggled.connect(checkbox.setChecked)
        return checkbox
