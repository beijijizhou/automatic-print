"""One data surface for live progress, phase timings and batch results."""
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout


def build_data_panel(window, summary, timings):
    summary.setTitle('排版数据 · 进度、耗时与总结')
    layout = summary.layout()
    for widget in (summary.info, summary.metrics, summary.progress):
        layout.removeWidget(widget)
    timings.setTitle('')
    timings.setObjectName('integratedTimings')
    timings.setStyleSheet('QGroupBox#integratedTimings { border: none; margin: 0; '
                         'padding: 0; background: transparent; }')
    left = QVBoxLayout()
    for widget in (summary.info, summary.metrics, summary.progress, window.progress,
                   window.status, window.current_file):
        left.addWidget(widget)
    window.status.setWordWrap(True)
    window.current_file.setWordWrap(True)
    left.addStretch()
    columns = QHBoxLayout()
    columns.addLayout(left, 1)
    columns.addWidget(timings, 1)
    layout.insertLayout(0, columns)
    return summary
