"""Send selected production batches to one online print machine."""

from dataclasses import asdict
from threading import Lock, Thread

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QMessageBox

from ...automation.api.machine_status import list_commands, list_machines, submit_command
from ...ui.machine_status_format import actionable_machines
from .remote_machine_dialog import RemoteMachineDialog
from .remote_queue import selected_batch_details, selection_text, workload_detail


def load_remote_targets():
    return {"machines": list_machines(), "commands": list_commands()}


class RemoteBatchDispatcher(QObject):
    machines_loaded = Signal(object)
    submitted = Signal(object)
    failed = Signal(str)

    def __init__(self, owner, *, fetch=load_remote_targets, submit=submit_command):
        super().__init__(owner)
        self.owner = owner
        self.fetch = fetch
        self.submit = submit
        self._lock = Lock()
        self._request = None
        self.machines_loaded.connect(self._choose_machine)
        self.submitted.connect(self._submitted)
        self.failed.connect(self._failed)

    def start(self, platform, batch_numbers, settings):
        if not self._lock.acquire(blocking=False):
            return False
        details = selected_batch_details(
            getattr(self.owner, "records", []), batch_numbers,
        )
        self._request = {
            "platform": str(platform),
            "batch_numbers": list(batch_numbers),
            "batch_details": details,
            "layout_settings": asdict(settings),
            "generate_prn": True,
        }
        self._set_busy(True, "正在读取可接收任务的在线打印机…")
        Thread(target=self._load_machines, daemon=True,
               name="remote-batch-machines").start()
        return True

    def _load_machines(self):
        try:
            self.machines_loaded.emit(self.fetch())
        except Exception as error:
            self.failed.emit(str(error))

    def _choose_machine(self, dashboard):
        if isinstance(dashboard, dict):
            rows = dashboard.get("machines") or []
            commands = dashboard.get("commands") or []
        else:
            rows, commands = dashboard, []
        machines = actionable_machines(rows, require_source=True)
        if not machines:
            self._finish("没有监控和 PrintExp 都在线且机器号不冲突的目标机器。")
            QMessageBox.warning(self.owner, "没有可用打印机", self.owner.remote_dispatch_status.text())
            return
        batches = self._request["batch_numbers"]
        request_text = (
            f"{self._request['platform']} · "
            f"{selection_text(self._request['batch_details'], batches)} · "
            f"批次 {'、'.join(batches)}"
        )
        dialog = RemoteMachineDialog(machines, commands, request_text, self.owner)
        if dialog.exec() != QDialog.Accepted:
            self._finish("已取消发送；批次选择保持不变。")
            return
        machine = dialog.selected_machine()
        if machine is None:
            self._finish("没有选中目标机器；批次选择保持不变。")
            return
        selected = str(machine.get("machine_name") or machine.get("machine_id"))
        detail = (
            f"目标：{selected}\n{workload_detail(machine, commands)}\n\n"
            f"本次发送：{request_text}\n"
            "目标机随后下载、排版、生成 PRN 并加载到 PrintExp；不会开始物理打印。"
        )
        if QMessageBox.question(self.owner, "确认发送到指定机器", detail) != QMessageBox.Yes:
            self._finish("已取消发送；批次选择保持不变。")
            return
        self._request["target_machine_id"] = str(machine["machine_id"])
        self._set_busy(True, f"正在向 {selected} 下达下载、排版和 PRN 任务…")
        Thread(target=self._submit, daemon=True, name="remote-batch-submit").start()

    def _submit(self):
        try:
            self.submitted.emit(self.submit(**self._request))
        except Exception as error:
            self.failed.emit(str(error))

    def _submitted(self, command):
        command_id = str(command.get("id") or "")
        self._finish(f"任务已发送：{command_id}；等待目标机领取并开始下载。")
        page = getattr(getattr(self.owner, "settings_host", None), "machine_status_page", None)
        if page is not None:
            page.refresh()

    def _failed(self, message):
        self._finish(f"远程任务发送失败：{message}")
        QMessageBox.critical(self.owner, "远程任务失败", str(message))

    def _finish(self, message):
        self._request = None
        if self._lock.locked():
            self._lock.release()
        self._set_busy(False, message)

    def _set_busy(self, busy, message):
        self.owner.remote_dispatch_button.setEnabled(not busy)
        self.owner.remote_dispatch_status.setText(message)
