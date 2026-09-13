"""Reuse generation controls on the main workbench, not in print settings."""
from PySide6.QtWidgets import QGroupBox, QVBoxLayout


def build_generation_panel(window):
    panel = QGroupBox('本次排版 · 处理进度')
    layout = QVBoxLayout(panel)
    for widget in (window.progress, window.status, window.current_file):
        layout.addWidget(widget)
    return panel
