"""GUI-thread presentation of worker-clock measurements."""
from time import perf_counter
from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)


class OperationTimingPanel(QGroupBox):
    def __init__(self, bridge, parent=None):
        super().__init__('本次排版 · 分步耗时', parent)
        self.data = None
        self.summary = QLabel('开始排版后显示各大步骤耗时')
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        copy = QPushButton('复制耗时')
        copy.clicked.connect(self.copy_report)
        header = QHBoxLayout()
        header.addWidget(self.summary, 1)
        header.addWidget(copy)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['操作步骤', '耗时', '占比 / 状态'])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 170)
        self.table.setMaximumHeight(140)
        self.note = QLabel('按实际执行阶段计时；大图延迟计算可能计入安全检查或保存。未执行的旋转比较不计时。')
        self.note.setWordWrap(True)
        self.note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.table)
        layout.addWidget(self.note)
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.refresh)
        bridge.layout_timings.connect(self.receive)

    def reset(self):
        self.timer.stop()
        self.data = None
        self.table.setRowCount(0)
        self.summary.setText('正在开始，等待后台计时…')
        self.note.setText('按实际执行阶段计时；大图延迟计算可能计入安全检查或保存。未执行的旋转比较不计时。')

    @Slot(object)
    def receive(self, data):
        self.data = data
        self.timer.start() if data['status'] == '运行中' else self.timer.stop()
        self.refresh()

    def refresh(self):
        if not self.data:
            return
        delta = max(0, perf_counter()-self.data['captured_at']) if self.data['status'] == '运行中' else 0
        total = self.data['total_seconds'] + delta
        rows = self.data['steps']
        values = [row['seconds'] + (delta if row['running'] else 0) for row in rows]
        self.table.setRowCount(len(rows))
        for index, (row, seconds) in enumerate(zip(rows, values)):
            state = '进行中' if row['running'] else '已完成'
            if self.data['status'] in ('失败', '已停止') and row['name'] == self.data.get('active_phase'):
                state = self.data['status']
            for column, text in enumerate((row['name'], f'{seconds:.2f} 秒', f'{seconds/max(total, .001):.1%} · {state}')):
                self.table.setItem(index, column, QTableWidgetItem(text))
        slowest = rows[values.index(max(values))]['name'] if values else '等待开始'
        self.summary.setText(f"{self.data['status']} · 总计 {total:.2f} 秒 · 最耗时：{slowest}")
        if any(row['name'] == '分段合成、安全检查与保存' for row in rows):
            self.note.setText('分段并行阶段显示实际总耗时，不把重叠时间相加；每段详细耗时和真实文件名记录在批次记录中。')

    def copy_report(self):
        lines = [self.summary.text()]
        lines.extend('：'.join(self.table.item(row, col).text() for col in range(3))
                     for row in range(self.table.rowCount()))
        lines.append(self.note.text())
        QApplication.clipboard().setText('\n'.join(lines))
