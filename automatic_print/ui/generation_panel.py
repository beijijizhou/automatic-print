"""One data surface for live progress, phase timings and batch results."""
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout


def build_data_panel(window, summary, timings):
    summary.setTitle('排版数据 · 进度、耗时与总结')
    layout = summary.layout()
    layout.removeWidget(summary.film_table)
    for widget in (summary.info, summary.metrics, summary.progress):
        layout.removeWidget(widget)
    timings.setTitle('')
    timings.setObjectName('integratedTimings')
    timings.setStyleSheet('QGroupBox#integratedTimings { border: none; margin: 0; '
                         'padding: 0; background: transparent; }')
    left = QVBoxLayout()
    for widget in (summary.info, summary.metrics, summary.progress):
        left.addWidget(widget)
    activity = QHBoxLayout()
    activity.addWidget(window.busy_spinner)
    activity.addWidget(window.progress, 1)
    left.addLayout(activity)
    for widget in (window.status, window.current_file):
        left.addWidget(widget)
    window.status.setWordWrap(True)
    window.current_file.setWordWrap(True)
    left.addStretch()
    columns = QHBoxLayout()
    columns.addLayout(left, 1)
    right = QVBoxLayout()
    right.addWidget(summary.film_table)
    right.addWidget(timings)
    columns.addLayout(right, 1)
    layout.insertLayout(0, columns)
    return summary
