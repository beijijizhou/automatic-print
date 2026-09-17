"""One data surface for live progress, phase timings and batch results."""
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout,
)


def build_data_panel(window, summary, timings):
    window.compact_status_only = True
    summary.setTitle('排版数据 · 耗时与总结')
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
    records = QGroupBox('批次处理记录 · 当前任务')
    record_layout = QVBoxLayout(records)
    window.batch_record = QPlainTextEdit()
    window.batch_record.setReadOnly(True)
    window.batch_record.setDocument(window.run_log.document())
    window.batch_record.setMaximumHeight(140)
    copy = QPushButton('复制批次记录')
    copy.clicked.connect(lambda: window.batch_record.selectAll())
    copy.clicked.connect(window.batch_record.copy)
    actions = QHBoxLayout()
    actions.addStretch()
    actions.addWidget(copy)
    record_layout.addLayout(actions)
    record_layout.addWidget(window.batch_record)
    window.batch_record_group = records
    layout.insertWidget(1, records)
    return summary
