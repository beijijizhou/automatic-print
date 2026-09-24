"""Machine picker that exposes live work and queued work before dispatch."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from .queue import compact_machine_text, workload_detail


class RemoteMachineDialog(QDialog):
    def __init__(self, machines, commands, request_text, parent=None):
        super().__init__(parent)
        self.machines = list(machines)
        self.commands = list(commands)
        self.setWindowTitle("选择目标打印机")
        self.resize(820, 300)
        instruction = QLabel(
            "选择后先实时检测目标机；收到 AutomaticPrint 和 PrintExp 回应后才允许发送。"
        )
        instruction.setWordWrap(True)
        self.target = QComboBox()
        for machine in self.machines:
            self.target.addItem(compact_machine_text(machine, self.commands))
        self.target.currentIndexChanged.connect(self._refresh_detail)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet(
            "padding:10px;background:#f3f7ff;border:1px solid #9bbcff;"
        )
        request = QLabel(f"本次准备发送：{request_text}")
        request.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("检测这台机器")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(instruction)
        layout.addWidget(self.target)
        layout.addWidget(self.detail)
        layout.addWidget(request)
        layout.addWidget(buttons)
        self._refresh_detail()

    def selected_machine(self):
        index = self.target.currentIndex()
        return self.machines[index] if 0 <= index < len(self.machines) else None

    def _refresh_detail(self):
        machine = self.selected_machine()
        self.detail.setText(
            workload_detail(machine, self.commands) if machine is not None else "没有可用机器。"
        )
