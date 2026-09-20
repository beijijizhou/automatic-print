"""One data surface for live progress, phase timings and batch results."""
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from .batch_status_board import BatchStatusBoard


def build_data_panel(window, summary, timings):
    window.compact_status_only = True
    summary.setTitle('排版数据 · 耗时与总结')
    layout = summary.layout()
    layout.removeWidget(summary.film_table)
    for widget in (summary.info, summary.metrics, summary.progress):
        layout.removeWidget(widget)
    # The top source card is the single visible batch identity. Keep this label
    # as an internal compatibility/data surface, but do not repeat it below.
    summary.info.hide()
    timings.setTitle('')
    timings.setObjectName('integratedTimings')
    timings.setStyleSheet('QGroupBox#integratedTimings { border: none; margin: 0; '
                         'padding: 0; background: transparent; }')
    left = QVBoxLayout()
    for widget in (summary.metrics, summary.progress):
        left.addWidget(widget)
    for widget in (window.busy_spinner, window.progress, window.status, window.current_file):
        widget.setParent(summary)
        widget.hide()
    left.addStretch()
    columns = QHBoxLayout()
    columns.addLayout(left, 1)
    right = QVBoxLayout()
    right.addWidget(summary.film_table)
    right.addWidget(timings)
    columns.addLayout(right, 1)
    layout.insertLayout(0, columns)
    window.batch_status_board = BatchStatusBoard(summary.parent())
    window.batch_status_board.setToolTip('选择批次，查看对应进度、分步耗时和排版结果。')
    window.batch_status_board.hide()
    return summary
