"""Developer-only, non-blocking focused checks for label/marker placement."""

import sys
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout


TEST_NODES = (
    'tests/test_marker_stack.py',
    'tests/test_embedded_cutter_marks.py',
)


class LabelPositionTestDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.process = None
        self.started_at = None
        self.setWindowTitle('开发者 · 标签位置安全短测')
        self.resize(740, 420)
        layout = QVBoxLayout(self)
        note = QLabel(
            '只运行标签、刀码位置的39组小样本测试；涵盖外置横向/纵向、左右侧、'
            '0°/±90°/180°和不同刀位模式。不读取DTF真实批次；'
            '只在本机临时目录生成样本，不触发打印。')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.status = QLabel('尚未开始')
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        self.run_button = QPushButton('运行标签位置短测')
        self.run_button.clicked.connect(self.start)
        layout.addWidget(self.run_button)
        self.clock = QTimer(self)
        self.clock.setInterval(200)
        self.clock.timeout.connect(self._tick)

    def is_running(self):
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def _tick(self):
        if self.started_at is not None:
            self.status.setText(f'正在测试标签位置 · {perf_counter()-self.started_at:.2f} 秒')

    def start(self):
        if self.is_running() or self.window.has_active_tasks():
            self.status.setText('已有任务运行中，请等待完成。')
            return
        if getattr(sys, 'frozen', False):
            self.status.setText('短测需要源码 Python 环境；安装包不包含 pytest。')
            return
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.started_at = perf_counter()
        self.log.clear()
        self.run_button.setEnabled(False)
        self.clock.start()
        self.process.start(sys.executable, ['-m', 'pytest', '-q', '-p', 'no:cacheprovider', *TEST_NODES])
        if not self.process.waitForStarted(3000):
            self.clock.stop()
            self.run_button.setEnabled(True)
            self.status.setText(f'测试未启动：{self.process.errorString()}')

    def _read_output(self):
        self.log.insertPlainText(bytes(self.process.readAllStandardOutput()).decode('utf-8', 'replace'))

    def _finished(self, exit_code, _status):
        self._read_output()
        self.clock.stop()
        elapsed = perf_counter()-self.started_at
        self.status.setText(f"{'通过' if exit_code == 0 else '失败'} · {elapsed:.2f} 秒 · 详见下方日志")
        self.run_button.setEnabled(True)

    def closeEvent(self, event):
        if self.is_running():
            self.hide()  # Closing the view must not cancel the running test.
            event.ignore()
            return
        super().closeEvent(event)
