"""Explicit user-triggered controls for a selected PrintExp machine."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from ..automation.api.machine_status.commands import submit_printer_action
from ..automation.api.printerexp.state_machine import (
    CLEAN_RESUME, PAUSED, PAUSE_PRINT, START_PRINT, control_allowed,
    start_button_text,
)
from .machine_command_ui import CommandSubmitter
from .machine_status_format import actionable_machines, machine_printer_state


class PrinterControlPanel(QGroupBox):
    command_submitted = Signal()

    def __init__(self, parent=None):
        super().__init__("打印机控制", parent)
        self.machines = []
        self.busy = False
        self.submitter = CommandSubmitter(self, submit=submit_printer_action)
        self.submitter.completed.connect(self._submitted)
        self.submitter.failed.connect(self._failed)
        self.target = QComboBox()
        self.target.currentIndexChanged.connect(self._sync_controls)
        self.start_button = QPushButton("开始打印")
        self.pause_button = QPushButton("暂停打印")
        self.clean_button = QPushButton("清洗后自动启动")
        self.start_button.clicked.connect(lambda: self._request("start_print"))
        self.pause_button.clicked.connect(lambda: self._request("pause_print"))
        self.clean_button.clicked.connect(lambda: self._request("clean_resume"))
        self.status = QLabel(
            "清洗后自动启动会先暂停打印，按 8 个喷头全部、强度中执行清洗，"
            "清洗命令完成后再继续打印。"
        )
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("目标打印机"))
        controls.addWidget(self.target, 1)
        controls.addWidget(self.start_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.clean_button)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.status)
        self.set_data([])

    def set_data(self, machines):
        selected = self.target.currentData()
        self.machines = actionable_machines(machines, require_source=True)
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
        self._sync_controls()

    def _request(self, action):
        target_name = self.target.currentText()
        if not target_name:
            return
        machine = self._selected_machine()
        if machine is None:
            return
        batch_name = str(machine.get("batch_name") or "").strip()
        if action == "start_print":
            paused = machine_printer_state(machine) == PAUSED
            title = "确认继续打印" if paused else "确认开始打印"
            detail = (
                f"目标打印机：{target_name}\n当前批次：{batch_name}\n\n"
                + ("目标机将核对已暂停状态和 PRN 文件名，然后继续打印。"
                   if paused else
                   "目标机将在执行前再次核对待打印状态、0% 进度和 PRN 文件名。")
            )
        elif action == "pause_print":
            title, detail = "确认暂停打印", f"将暂停 {target_name} 当前正在打印的任务。"
        else:
            title = "确认清洗后自动启动"
            detail = (
                f"将自动暂停 {target_name}，确认暂停后执行清洗；"
                "参数固定为 8 个喷头全部、强度中；只有清洗命令完成才会自动继续打印。"
            )
        if QMessageBox.question(self, title, detail) != QMessageBox.Yes:
            return
        request = {"target_machine_id": self.target.currentData(), "action": action}
        if action == "start_print":
            request["expected_batch_name"] = batch_name
        if self.submitter.start(request):
            self.busy = True
            self._sync_controls()
            self.status.setText("正在向目标打印机提交控制指令…")

    def _submitted(self, command):
        self.busy = False
        self._sync_controls()
        self.status.setText(f"指令已下达：{command.get('id')}；请在下方任务状态查看结果。")
        self.command_submitted.emit()

    def _failed(self, message):
        self.busy = False
        self._sync_controls()
        self.status.setText(f"控制指令下达失败：{message}")

    def _selected_machine(self):
        machine_id = str(self.target.currentData() or "")
        return next(
            (item for item in self.machines if str(item.get("machine_id")) == machine_id),
            None,
        )

    def _sync_controls(self, *_args):
        machine = self._selected_machine()
        state = machine_printer_state(machine or {})
        available = machine is not None and not self.busy
        self.start_button.setText(start_button_text(state))
        self.target.setEnabled(bool(self.machines) and not self.busy)
        facts = {
            "progress": machine.get("progress_percent") if machine else None,
            "task_name_verified": (
                (machine.get("batch_info") or {}).get("task_name_verified") is True
                if machine else False
            ),
            "batch_name": machine.get("batch_name") if machine else "",
        }
        self.start_button.setEnabled(
            available and control_allowed(START_PRINT, state, **facts)
        )
        self.pause_button.setEnabled(
            available and control_allowed(PAUSE_PRINT, state, **facts)
        )
        self.clean_button.setEnabled(
            available and control_allowed(CLEAN_RESUME, state, **facts)
        )
