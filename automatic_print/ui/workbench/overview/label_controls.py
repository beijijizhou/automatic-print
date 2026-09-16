"""Mirrored everyday label controls at the top of the batch overview."""

from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, QPushButton

from ....layout_engine.labels import compact_label_text
from ...quick_fields import quick_fields


def mirrored_checkbox(text, source):
    checkbox = QCheckBox(text)
    checkbox.setChecked(source.isChecked())
    checkbox.toggled.connect(source.setChecked)
    source.toggled.connect(checkbox.setChecked)
    return checkbox


def build_label_controls(panel, label, window):
    panel.text = QLineEdit(label.text_template.text())
    panel.text.setPlaceholderText("手动输入标签文字；机器号和序号自动显示")
    panel.text.textChanged.connect(label.text_template.setText)
    label.text_template.textChanged.connect(panel.text.setText)
    panel.text.editingFinished.connect(
        lambda: panel.text.setText(compact_label_text(panel.text.text()))
    )

    panel.font_size = QDoubleSpinBox()
    panel.font_size.setRange(label.font_size.minimum(), label.font_size.maximum())
    panel.font_size.setDecimals(1)
    panel.font_size.setValue(label.font_size.value())
    panel.font_size.valueChanged.connect(label.font_size.setValue)
    label.font_size.valueChanged.connect(panel.font_size.setValue)
    panel.fit_height = mirrored_checkbox(
        "限制整段高度，字号不超过手动设置", label.fit_height
    )
    panel.detect_region = mirrored_checkbox(
        "识别膜标签并动态等高适配", label.detect_region
    )
    panel.reference_height = QDoubleSpinBox()
    panel.reference_height.setRange(2, 100)
    panel.reference_height.setDecimals(1)
    panel.reference_height.setValue(label.reference_height.value())
    panel.reference_height.valueChanged.connect(label.reference_height.setValue)
    label.reference_height.valueChanged.connect(panel.reference_height.setValue)
    for control in (panel.reference_height, panel.fit_height, panel.font_size):
        label.detect_region.toggled.connect(
            lambda value, target=control: target.setEnabled(not value)
        )
        control.setEnabled(not label.detect_region.isChecked())

    panel.enabled = mirrored_checkbox("添加标签", label.enabled)
    panel.follow_qr = mirrored_checkbox("自动与膜标签水平对齐", label.follow_qr)
    panel.follow_qr.setEnabled(label.follow_qr.isEnabled())
    panel.machine = _mirror_combo(label.machine)
    panel.machine.currentIndexChanged.connect(label.machine.setCurrentIndex)
    label.machine.currentIndexChanged.connect(panel.machine.setCurrentIndex)
    label.machine.currentIndexChanged.connect(
        lambda *_: window.preferences.setValue(
            "layout/machine_number", label.machine.currentData()
        )
    )
    panel.position = _mirror_combo(label.position)
    panel.position.currentIndexChanged.connect(label.position.setCurrentIndex)
    label.position.currentIndexChanged.connect(panel.position.setCurrentIndex)
    panel.position.currentIndexChanged.connect(
        lambda *_: panel.follow_qr.setEnabled(label.follow_qr.isEnabled())
    )

    date_button = QPushButton("添加日期")
    date_button.clicked.connect(lambda: _add_date(panel))
    panel.sequence = mirrored_checkbox("序号从 1 到最后一张", label.sequence)
    panel.platform = QComboBox()
    panel.platform.setEditable(True)
    for index in range(label.platform.count()):
        panel.platform.addItem(label.platform.itemText(index))
    panel.platform.setCurrentText(label.platform.currentText())
    panel.platform.currentTextChanged.connect(label.platform.setCurrentText)
    label.platform.currentTextChanged.connect(panel.platform.setCurrentText)
    panel.platform.setStyleSheet("QComboBox { font-size: 20px; font-weight: bold; }")
    panel.platform_font_height = QDoubleSpinBox()
    panel.platform_font_height.setRange(0, 50)
    panel.platform_font_height.setDecimals(1)
    panel.platform_font_height.setSuffix(" 毫米")
    panel.platform_font_height.setSpecialValueText("自动：膜标签等高")
    panel.platform_font_height.setValue(label.platform_font_height.value())
    panel.platform_font_height.valueChanged.connect(label.platform_font_height.setValue)
    label.platform_font_height.valueChanged.connect(panel.platform_font_height.setValue)

    form = quick_fields(panel, date_button, window)
    for control in (
        panel.font_size,
        panel.fit_height,
        panel.detect_region,
        panel.reference_height,
        panel.position,
        panel.enabled,
        panel.follow_qr,
    ):
        control.setParent(panel)
        control.hide()
    return form


def _mirror_combo(source):
    combo = QComboBox()
    for index in range(source.count()):
        combo.addItem(source.itemText(index), source.itemData(index))
    combo.setCurrentIndex(source.currentIndex())
    return combo


def _add_date(panel) -> None:
    if "{日期}" not in panel.text.text():
        panel.text.setText(panel.text.text().rstrip() + "－{日期}")
