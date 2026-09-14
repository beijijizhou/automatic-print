"""Developer-only transparent algorithm costs and existing batch timing data."""
from time import perf_counter
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QPushButton, QPlainTextEdit, QApplication)
from ..layout_engine.algorithm_costs import VARIABLES, STEPS
from ..layout_engine.operation_timing import timing_report


class AlgorithmCostsPage(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        layout = QVBoxLayout(self)
        note = QLabel(VARIABLES+'\n理论上界不是当前批次耗时，也不是全局最优证明；多线程只影响执行时间，不改变复杂度。')
        note.setWordWrap(True)
        note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(note)
        self.table = QTableWidget(len(STEPS), 4)
        self.table.setHorizontalHeaderLabels(['步骤', '算法开销', '原因 / 规模', '现状 / 优化方向'])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 300)
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, values in enumerate(STEPS):
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.resizeRowsToContents()
        layout.addWidget(self.table, 2)
        self.selected = QLabel()
        self.selected.setWordWrap(True)
        self.selected.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.selected)
        def describe(row, *_):
            if row >= 0:
                self.selected.setText('\n'.join(STEPS[row]))
        self.table.currentCellChanged.connect(describe)
        self.table.setCurrentCell(5, 0)
        self.actual = QPlainTextEdit()
        self.actual.setReadOnly(True)
        layout.addWidget(self.actual, 1)
        copy = QPushButton('复制算法开销与本次耗时')
        copy.clicked.connect(self.copy_report)
        layout.addWidget(copy)
        window.worker_bridge.layout_timings.connect(lambda *_: self.refresh())
        window.worker_bridge.layout_preview.connect(lambda *_: self.refresh())
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(lambda: self.refresh() if self.isVisible() else None)
        self.timer.start()
        self.refresh()

    def refresh(self):
        panel = self.window.automation_home.label_quick_panel
        payload = panel.preview.batch_payload
        scale = '当前批次尚未读取；本页不会自动扫描图片。'
        if payload:
            scale = f"当前主界面批次：{len(payload['planned'])}张图片 · "
            scale += f"{len(payload.get('analysis', {}).get('orders', []))}个分析组；实际k未记录，不伪造估计。"
        data = panel.timings.data
        if data and data['status'] == '运行中':
            delta = max(0, perf_counter()-data['captured_at'])
            data = dict(data, total_seconds=data['total_seconds']+delta,
                        steps=[dict(step, seconds=step['seconds']+(delta if step['running'] else 0))
                               for step in data['steps']])
        text = timing_report(data) if data else '尚无实测耗时；开始排版后更新。'
        self.actual.setPlainText(scale+'\n\n主界面任务实测耗时（不代表批量窗口全部任务）：\n'+text)

    def copy_report(self):
        text = VARIABLES+'\n\n'+'\n'.join(' · '.join(row) for row in STEPS)
        QApplication.clipboard().setText(text+'\n\n'+self.actual.toPlainText())
