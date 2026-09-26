"""Explicit remote launch control for the AutomaticPrint desktop UI."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout,
)

from ..automation.api.machine_status.commands import submit_application_launch
from .machine_command_ui import CommandSubmitter
from .machine_status_format import machine_display_name, machine_slots


class SoftwareLaunchPanel(QGroupBox):
    command_submitted = Signal()

    def __init__(self, parent=None):
        super().__init__("AutomaticPrint 软件控制", parent)
        self.machines = []
        self.submitter = CommandSubmitter(self, submit=submit_application_launch)
        self.submitter.completed.connect(self._submitted)
        self.submitter.failed.connect(self._failed)
        self.target = QComboBox()
        self.button = QPushButton("远程打开 AutomaticPrint")
        self.button.clicked.connect(self._request)
        self.status = QLabel(
            "只启动目标电脑上的 AutomaticPrint 主界面，不控制 PrintExp；"
            "目标电脑必须已登录 Windows，且后台监控仍在运行。"
        )
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("目标电脑"))
        controls.addWidget(self.target, 1)
        controls.addWidget(self.button)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.status)
        self.set_data([])

    def set_data(self, machines):
        selected = self.target.currentData()
        self.machines = [
            item for item in machine_slots(machines, 11)
            if item is not None and item.get("machine_id")
            and not item.get("identity_conflict")
        ]
        self.target.clear()
        for machine in self.machines:
            self.target.addItem(machine_display_name(machine), str(machine["machine_id"]))
        if selected:
            index = self.target.findData(selected)
            if index >= 0:
                self.target.setCurrentIndex(index)
        self._sync()

    def _request(self):
        name = self.target.currentText()
        if not name:
            return
        detail = (
            f"将在 {name} 上启动 AutomaticPrint 主界面。\n\n"
            "如果主界面已经运行，目标机只返回“已经运行”，不会重复打开。"
        )
        if QMessageBox.question(self, "确认远程打开软件", detail) != QMessageBox.Yes:
            return
        if self.submitter.start({"target_machine_id": self.target.currentData()}):
            self.target.setEnabled(False)
            self.button.setEnabled(False)
            self.status.setText("唤起指令已发送，正在等待目标电脑回执…")

    def _submitted(self, command):
        self._sync()
        self.status.setText(f"指令已发送：{command.get('id')}；请在任务状态查看回执。")
        self.command_submitted.emit()

    def _failed(self, message):
        self._sync()
        self.status.setText(f"远程打开失败：{message}")

    def _sync(self):
        busy = self.submitter._lock.locked()
        self.target.setEnabled(bool(self.machines) and not busy)
        self.button.setEnabled(bool(self.machines) and not busy)
