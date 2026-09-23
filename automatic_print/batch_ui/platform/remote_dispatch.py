"""Send selected production batches to one online print machine."""

from dataclasses import asdict
from threading import Lock, Thread

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QInputDialog, QMessageBox

from ...automation.api.machine_status import list_machines, submit_command
from ...ui.machine_status_format import actionable_machines


class RemoteBatchDispatcher(QObject):
    machines_loaded = Signal(object)
    submitted = Signal(object)
    failed = Signal(str)

    def __init__(self, owner, *, fetch=list_machines, submit=submit_command):
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
        self._request = {
            "platform": str(platform),
            "batch_numbers": list(batch_numbers),
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

    def _choose_machine(self, rows):
        machines = actionable_machines(rows, require_source=True)
        if not machines:
            self._finish("没有监控和 PrintExp 都在线且机器号不冲突的目标机器。")
            QMessageBox.warning(self.owner, "没有可用打印机", self.owner.remote_dispatch_status.text())
            return
        labels = [str(item.get("machine_name") or item.get("machine_id")) for item in machines]
        selected, accepted = QInputDialog.getItem(
            self.owner, "选择目标打印机", "目标机器", labels, 0, False,
        )
        if not accepted:
            self._finish("已取消发送；批次选择保持不变。")
            return
        machine = machines[labels.index(selected)]
        batches = self._request["batch_numbers"]
        detail = (
            f"让 {selected} 下载并排版 {len(batches)} 个批次，随后生成 PRN "
            "并加载到 PrintExp。不会开始物理打印。"
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
