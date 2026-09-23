"""Explicit user-triggered controls for a selected PrintExp machine."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from ..automation.api.machine_status.commands import submit_printer_action
from .machine_command_ui import CommandSubmitter


class PrinterControlPanel(QGroupBox):
    command_submitted = Signal()

    def __init__(self, parent=None):
        super().__init__("打印机控制", parent)
        self.machines = []
        self.submitter = CommandSubmitter(self, submit=submit_printer_action)
        self.submitter.completed.connect(self._submitted)
        self.submitter.failed.connect(self._failed)
        self.target = QComboBox()
        self.pause_button = QPushButton("暂停打印")
        self.clean_button = QPushButton("清洗后自动启动")
        self.pause_button.clicked.connect(lambda: self._request("pause_print"))
        self.clean_button.clicked.connect(lambda: self._request("clean_resume"))
        self.status = QLabel(
            "先暂停，再执行清洗后自动启动；只有确认清洗结束才会继续打印。"
        )
        self.status.setWordWrap(True)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("目标打印机"))
        controls.addWidget(self.target, 1)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.clean_button)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.status)
        self.set_data([])

    def set_data(self, machines):
        selected = self.target.currentData()
        self.machines = [
            item for item in machines
            if item.get("agent_online") and item.get("source_online")
        ]
        self.target.clear()
        for machine in self.machines:
            self.target.addItem(
                str(machine.get("machine_name") or machine.get("machine_id")),
                str(machine.get("machine_id")),
            )
        if selected:
            index = self.target.findData(selected)
            if index >= 0:
                self.target.setCurrentIndex(index)
        self._set_enabled(bool(self.machines))

    def _request(self, action):
        target_name = self.target.currentText()
        if not target_name:
            return
        if action == "pause_print":
            title, detail = "确认暂停打印", f"将暂停 {target_name} 当前正在打印的任务。"
        else:
            title = "确认清洗后自动启动"
            detail = (
                f"将要求 {target_name} 必须已暂停，然后执行清洗；"
                "只有确认清洗结束才会自动继续打印。"
            )
        if QMessageBox.question(self, title, detail) != QMessageBox.Yes:
            return
        if self.submitter.start({
            "target_machine_id": self.target.currentData(), "action": action,
        }):
            self._set_enabled(False)
            self.status.setText("正在向目标打印机提交控制指令…")

    def _submitted(self, command):
        self._set_enabled(bool(self.machines))
        self.status.setText(f"指令已下达：{command.get('id')}；请在下方任务状态查看结果。")
        self.command_submitted.emit()

    def _failed(self, message):
        self._set_enabled(bool(self.machines))
        self.status.setText(f"控制指令下达失败：{message}")

    def _set_enabled(self, enabled):
        self.target.setEnabled(enabled)
        self.pause_button.setEnabled(enabled)
        self.clean_button.setEnabled(enabled)
