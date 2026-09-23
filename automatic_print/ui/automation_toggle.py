"""One-click fleet automation pause and authenticated LAN wake-up."""

from threading import Thread

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton

from ..runtime.monitoring.control import automation_enabled, broadcast_automation


class _AutomationWorker(QObject):
    finished = Signal(bool, str)


class AutomationToggle(QGroupBox):
    changed = Signal(bool)

    def __init__(self, parent=None, *, read=automation_enabled, write=broadcast_automation):
        super().__init__("全部机器自动化", parent)
        self.read = read
        self.write = write
        self.enabled = bool(self.read())
        self.worker = _AutomationWorker(self)
        self.worker.finished.connect(self._finished)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.button = QPushButton()
        self.button.clicked.connect(self.toggle)
        layout = QHBoxLayout(self)
        layout.addWidget(self.status, 1)
        layout.addWidget(self.button)
        self._render()

    def toggle(self):
        target = not self.enabled
        self.button.setEnabled(False)
        self.status.setText("正在切换后台自动化…")
        Thread(
            target=self._apply, args=(target,), daemon=True,
            name="automation-toggle",
        ).start()

    def _apply(self, target):
        try:
            result = bool(self.write(target))
            action = "开启" if result else "关闭"
            message = f"已向局域网发送全部机器自动化{action}信号。"
            self.worker.finished.emit(result, message)
        except Exception as error:
            self.worker.finished.emit(self.enabled, f"切换失败：{error}")

    def _finished(self, enabled, message):
        self.enabled = bool(enabled)
        self._render(message)
        self.button.setEnabled(True)
        self.changed.emit(self.enabled)

    def _render(self, message=None):
        if self.enabled:
            self.button.setText("一键关闭全部自动化")
            default = "已开启：机器状态、远程任务和打印控制连接 Supabase。"
        else:
            self.button.setText("一键开启全部自动化")
            default = "已关闭：Supabase 后台调用为 0；电脑和 PrintExp 保持运行。"
        self.status.setText(message or default)
