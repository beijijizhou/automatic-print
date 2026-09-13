"""Reuse generation controls on the main workbench, not in print settings."""
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QPushButton


def build_generation_panel(window):
    panel = QGroupBox('本次排版 · 处理进度')
    layout = QVBoxLayout(panel)
    for widget in (window.progress, window.status, window.current_file,
                   window.stop_generation_button):
        layout.addWidget(widget)
    details = QPushButton('展开处理日志')
    details.setCheckable(True)
    details.toggled.connect(window.run_log.setVisible)
    details.toggled.connect(lambda shown: details.setText('收起处理日志' if shown else '展开处理日志'))
    layout.addWidget(details)
    layout.addWidget(window.run_log)
    window.run_log.hide()
    return panel
