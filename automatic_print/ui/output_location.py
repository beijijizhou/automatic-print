"""Source-following output defaults with a persistent manual override."""
from pathlib import Path
from PySide6.QtWidgets import QCheckBox, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout


def build_output_location(window, default):
    prefs = window.preferences
    window.custom_output_location = prefs.value('output/custom_location',
                                                prefs.value('output_location', default, str), str)
    window.output_location = QLineEdit(window.custom_output_location)
    window.output_beside_source = QCheckBox('默认保存到图片文件夹同级的“切膜机文件”（直接存放排版图）')
    window.output_beside_source.setChecked(prefs.value('output/beside_source', True, bool))
    button = QPushButton('选择保存位置…')
    button.clicked.connect(window.choose_output_location)

    def refresh(*_args):
        automatic = window.output_beside_source.isChecked()
        window.output_location.setReadOnly(automatic)
        button.setEnabled(not automatic)
        source = window.folder.text().strip()
        target = str(Path(source).parent) if source else ''
        window.output_location.setText(target if automatic else window.custom_output_location)

    def remember(text):
        if not window.output_beside_source.isChecked():
            window.custom_output_location = text

    window.output_location.textChanged.connect(remember)
    window.folder.textChanged.connect(refresh)
    window.output_beside_source.toggled.connect(refresh)
    refresh()
    row = QHBoxLayout()
    row.addWidget(window.output_location)
    row.addWidget(button)
    layout = QVBoxLayout()
    layout.addWidget(window.output_beside_source)
    layout.addLayout(row)
    return layout


def output_base(window, source):
    return source.parent if window.output_beside_source.isChecked() else Path(window.output_location.text().strip())
