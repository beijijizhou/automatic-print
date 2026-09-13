"""Compact common fields and a persistent, highlighted source identity."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout


def quick_fields(panel, date_button, window):
    row = QHBoxLayout()
    controls = (("标签与文字", panel.text, 3), ("生产平台", panel.platform, 1),
                ("平台文字高度", panel.platform_font_height, 1), ("机器号", panel.machine, 0))
    for name, control, stretch in controls:
        row.addWidget(QLabel(name))
        row.addWidget(control, stretch)
        control.setMinimumWidth(60)
        control.setToolTip(name)
    panel.platform_font_height.setMaximumWidth(125)
    panel.machine.setMaximumWidth(75)
    panel.platform.setMaximumWidth(145)
    panel.text.setMinimumWidth(120)
    panel.sequence.setParent(panel)
    panel.sequence.hide()  # Canonical sequence option remains in label settings.
    date_button.setParent(panel)
    date_button.hide()  # Date insertion remains available in the full settings.
    panel.selected_source = QLabel()
    panel.selected_source.setWordWrap(True)
    panel.selected_source.setTextInteractionFlags(Qt.TextSelectableByMouse)
    def show_source(value):
        path = Path(value.strip()) if value.strip() else None
        panel.selected_source.setText(f'已选择：{path.name}  ·  {path}' if path else '尚未选择图片文件夹')
        panel.selected_source.setStyleSheet('QLabel { background: #dbeafe; color: #1e40af; '
            'border: 1px solid #60a5fa; border-radius: 5px; padding: 7px; font-weight: bold; }'
            if path else 'QLabel { color: #64748b; padding: 5px; }')
    window.folder.textChanged.connect(show_source)
    show_source(window.folder.text())
    layout = QVBoxLayout()
    layout.addLayout(row)
    layout.addWidget(panel.selected_source)
    return layout
