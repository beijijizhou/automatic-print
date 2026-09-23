"""Controls for safely submitting and reviewing remote production commands."""

from dataclasses import asdict
import re
from threading import Lock, Thread

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..automation.api.machine_status.commands import submit_command
from .machine_status_format import actionable_machines


class CommandSubmitter(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None, submit=submit_command):
        super().__init__(parent)
        self.submit = submit
        self._lock = Lock()

    def start(self, request):
        if not self._lock.acquire(blocking=False):
            return False
        Thread(target=self._run, args=(request,), daemon=True, name="machine-command-submit").start()
        return True

    def _run(self, request):
        try:
            self.completed.emit(self.submit(**request))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self._lock.release()


class MachineCommandDialog(QDialog):
    def __init__(self, machines, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下达远程下载排版任务")
        self.resize(560, 360)
        self.target = QComboBox()
        for machine in machines:
            self.target.addItem(
                str(machine.get("machine_name") or machine.get("machine_id")),
                str(machine.get("machine_id")),
            )
        self.platform = QComboBox()
        self.platform.addItems(("Haloo", "隆丰", "莆田"))
        self.batches = QPlainTextEdit()
        self.batches.setPlaceholderText("每行一个 12 位批次号，最多 20 个")
        self.batches.setMaximumHeight(110)
        self.generate_prn = QCheckBox("生成 PRN 并加载到 PrintExp（不会开始物理打印）")
        self.generate_prn.setChecked(True)
        note = QLabel(
            "目标机使用自己的 ERP 登录状态和本地下载目录；排版参数取自当前控制端，"
            "机器编号使用目标机本地设置。任务 30 分钟未领取会自动过期。"
        )
        note.setWordWrap(True)
        form = QFormLayout()
        form.addRow("目标打印机", self.target)
        form.addRow("生产平台", self.platform)
        form.addRow("生产批次", self.batches)
        form.addRow("完成方式", self.generate_prn)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("确认下达")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def batch_numbers(self):
        return [
            value for value in re.split(r"[\s,，;；]+", self.batches.toPlainText().strip())
            if value
        ]


class RemoteCommandPanel(QGroupBox):
    command_submitted = Signal()

    def __init__(self, host_window, parent=None):
        super().__init__("远程下载排版任务", parent)
        self.host_window = host_window
        self.machines = []
        self.submitter = CommandSubmitter(self)
        self.submitter.completed.connect(self._submitted)
        self.submitter.failed.connect(self._failed)
        self.submit_button = QPushButton("向打印机下达任务")
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self.open_dialog)
        self.status = QLabel("只有监控在线的机器可以领取远程任务。")
        self.status.setWordWrap(True)
        header = QHBoxLayout()
        header.addWidget(self.status, 1)
        header.addWidget(self.submit_button)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("目标机器", "任务", "状态", "当前步骤", "下达人"))
        self.table.verticalHeader().setVisible(False)
        self.table.setMaximumHeight(190)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.table)

    def set_data(self, machines, commands):
        self.machines = actionable_machines(machines)
        self.submit_button.setEnabled(bool(self.machines))
        self.table.setRowCount(min(10, len(commands)))
        names = {str(item.get("machine_id")): item.get("machine_name") for item in machines}
        for row, command in enumerate(commands[:10]):
            payload = command.get("payload") or {}
            batches = payload.get("batch_numbers") or []
            values = (
                names.get(str(command.get("target_machine_id"))) or str(command.get("target_machine_id") or ""),
                _command_summary(command.get("action"), payload, batches),
                _command_status(command.get("status")),
                command.get("phase") or command.get("error_message") or "等待目标机领取",
                command.get("requested_by_name") or "—",
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))

    def open_dialog(self):
        dialog = MachineCommandDialog(self.machines, self)
        if dialog.exec() != QDialog.Accepted:
            return
        batches = dialog.batch_numbers()
        if not batches or len(batches) > 20 or any(not re.fullmatch(r"\d{12}", item) for item in batches):
            QMessageBox.warning(self, "批次号不正确", "请输入 1–20 个完整的 12 位批次号。")
            return
        if len(set(batches)) != len(batches):
            QMessageBox.warning(self, "批次号重复", "同一条任务中不能包含重复批次号。")
            return
        try:
            layout_settings = asdict(self.host_window._layout_settings())
        except Exception as error:
            QMessageBox.warning(self, "排版参数不可用", str(error))
            return
        target_name = dialog.target.currentText()
        detail = (
            f"将让 {target_name} 下载并排版 {len(batches)} 个批次。"
            + ("完成后生成 PRN 并加载 PrintExp，但不会开始物理打印。" if dialog.generate_prn.isChecked()
               else "完成后只生成排版 PNG。")
        )
        if QMessageBox.question(self, "确认远程任务", detail) != QMessageBox.Yes:
            return
        request = {
            "target_machine_id": dialog.target.currentData(),
            "platform": dialog.platform.currentText(),
            "batch_numbers": batches,
            "layout_settings": layout_settings,
            "generate_prn": dialog.generate_prn.isChecked(),
        }
        if self.submitter.start(request):
            self.submit_button.setEnabled(False)
            self.status.setText("正在向 Supabase 提交远程任务…")

    def _submitted(self, command):
        self.submit_button.setEnabled(bool(self.machines))
        self.status.setText(f"任务已下达：{command.get('id')}；等待目标机领取。")
        self.command_submitted.emit()

    def _failed(self, message):
        self.submit_button.setEnabled(bool(self.machines))
        self.status.setText(f"任务下达失败：{message}")


def _command_status(status):
    return {
        "queued": "等待领取", "claimed": "已领取", "running": "执行中",
        "succeeded": "已完成", "failed": "失败", "cancelled": "已取消", "expired": "已过期",
    }.get(str(status), str(status or "未知"))


def _command_summary(action, payload, batches):
    if action == "pause_print":
        return "暂停打印"
    if action == "clean_resume":
        return "清洗后自动启动"
    return f"{payload.get('platform') or '—'} · {', '.join(map(str, batches))}"
