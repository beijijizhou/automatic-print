"""One data surface for live progress, phase timings and batch results."""
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout
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
    record_header = QHBoxLayout()
    record_header.addWidget(QLabel('批次处理记录 · 当前所选批次'))
    record_header.addStretch()
    copy_record = QPushButton('复制记录')
    record_header.addWidget(copy_record)
    layout.insertLayout(1, record_header)
    window.batch_record_view = QPlainTextEdit(summary)
    window.batch_record_view.setReadOnly(True)
    window.batch_record_view.setMaximumHeight(160)
    window.batch_record_view.setMinimumHeight(90)
    window.batch_record_view.setPlainText('尚无批次记录；开始排版后在这里显示。')
    layout.insertWidget(2, window.batch_record_view)
    copy_record.clicked.connect(
        lambda: QApplication.clipboard().setText(window.batch_record_view.toPlainText())
    )
    window.run_log.textChanged.connect(lambda: refresh_batch_record(window))
    window.batch_status_board = BatchStatusBoard(summary.parent())
    window.batch_status_board.setToolTip('选择批次，查看对应进度、分步耗时和排版结果。')
    window.batch_status_board.hide()
    return summary


def refresh_batch_record(window):
    """Show only the selected batch's short live log; full reports stay in the dialog."""
    lines = window.run_log.toPlainText().splitlines()
    preview = getattr(window, 'generation_preview', None)
    bulk = getattr(window, 'bulk_controller', None)
    if getattr(preview, 'mode', None) == 'multiple' and bulk is not None:
        index = window.batch_status_board.currentIndex()
        if 0 <= index < len(bulk.folders):
            folder = bulk.folders[index]
            prefixes = (folder.name + '：', str(folder) + '：')
            lines = [str(folder), *(line for line in lines if line.startswith(prefixes))]
        else:
            lines = ['正在扫描批次文件夹…']
    content = '\n'.join(lines) or '尚无批次记录；开始排版后在这里显示。'
    if window.batch_record_view.toPlainText() != content:
        window.batch_record_view.setPlainText(content)
        bar = window.batch_record_view.verticalScrollBar()
        bar.setValue(bar.maximum())
