"""On-demand PrintExp history view shared by every machine node."""

from threading import Lock, Thread
from time import monotonic, sleep

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from ..automation.api.machine_status.commands import (
    cancel_command, consume_command_result, get_command, submit_history_request,
)
from ..automation.api.printerexp.history import read_print_history
from .machine_status_format import machine_display_name, machine_slots


class HistoryLoader(QObject):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = Lock()

    def start(self, target_id, local=False):
        if not self._lock.acquire(blocking=False):
            return False
        Thread(
            target=self._run, args=(str(target_id), bool(local)), daemon=True,
            name="printer-history-read",
        ).start()
        return True

    def _run(self, target_id, local):
        try:
            result = read_print_history(limit=50) if local else _read_remote(target_id)
            self.loaded.emit(result)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self._lock.release()


def _read_remote(target_id, *, timeout=15):
    command = submit_history_request(target_id, limit=500, days=2)
    command_id = str(command.get("id") or "")
    if not command_id:
        raise RuntimeError("目标机没有返回查询编号。")
    deadline = monotonic() + float(timeout)
    while monotonic() < deadline:
        current = get_command(command_id)
        status = str(current.get("status") or "")
        if status == "succeeded":
            return consume_command_result(command_id)
        if status in {"failed", "cancelled", "expired"}:
            message = current.get("error_message") or current.get("phase") or status
            if status == "failed":
                consume_command_result(command_id)
            raise RuntimeError(str(message))
        sleep(0.5)
    try:
        cancel_command(command_id)
    except Exception:
        pass
    raise TimeoutError("15 秒内未收到目标机的打印历史。")


class PrinterHistoryPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("PrintExp 本机历史（按需读取）", parent)
        self.machines = []
        self.loader = HistoryLoader(self)
        self.loader.loaded.connect(self._loaded)
        self.loader.failed.connect(self._failed)
        self.target = QComboBox()
        self.read_button = QPushButton("读取打印历史")
        self.read_button.clicked.connect(self.read)
        self.status = QLabel("默认读取今天和昨天；不会建立历史数据库或持续同步。")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ("记录序号", "开始时间", "结束时间", "用时", "PRN 文件", "PrintExp 原始路径")
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("目标打印机"))
        controls.addWidget(self.target, 1)
        controls.addWidget(self.read_button)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.status)
        layout.addWidget(self.table, 1)
        self.set_data([])

    def set_data(self, machines):
        selected = self.target.currentData()
        self.machines = [item for item in machine_slots(machines) if item and not item.get("identity_conflict")]
        self.target.clear()
        for machine in self.machines:
            self.target.addItem(machine_display_name(machine), {
                "id": str(machine.get("machine_id") or ""),
                "local": bool(machine.get("is_local")),
            })
        if selected:
            for index in range(self.target.count()):
                if self.target.itemData(index) == selected:
                    self.target.setCurrentIndex(index)
                    break
        self.read_button.setEnabled(bool(self.machines))

    def read(self):
        target = self.target.currentData() or {}
        if not target.get("id"):
            return
        if self.loader.start(target["id"], target.get("local", False)):
            self.read_button.setEnabled(False)
            self.status.setText(f"正在向 {self.target.currentText()} 读取 PrintExp 本地历史…")

    def _loaded(self, result):
        records = result.get("records") or []
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = (
                record.get("sequence"), _time(record.get("started_at")),
                _time(record.get("finished_at")), _duration(record.get("duration_seconds")),
                record.get("task_name"), record.get("source_path"),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value or "—")))
        self.read_button.setEnabled(bool(self.machines))
        diagnostics = result.get("diagnostics") or {}
        if diagnostics.get("task_file_fallback"):
            self.status.setText(
                f"目标机日志无法提供打印时间；当前显示 PrintExp 本地任务记录"
                f" {result.get('total_records', 0)} 条，开始和结束时间不可用。"
            )
        elif diagnostics.get("range_fallback"):
            files = "、".join(diagnostics.get("log_files_checked") or []) or "未知"
            self.status.setText(
                f"目标机缺少今天/昨天日志；当前显示最近可用日志 {files} 中的"
                f" {result.get('total_records', 0)} 条记录，时间不是今天/昨天。"
            )
        else:
            self.status.setText(
                f"今天和昨天共 {result.get('total_records', 0)} 条；当前显示 {len(records)} 条。"
            )

    def _failed(self, message):
        self.read_button.setEnabled(bool(self.machines))
        self.status.setText(f"打印历史读取失败：{message}")


def _time(value):
    return str(value or "").replace("T", " ") or "—"


def _duration(value):
    seconds = max(0, int(value or 0))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
