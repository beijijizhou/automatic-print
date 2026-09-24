"""Shared manual availability override for the machine status page."""

from threading import Lock, Thread

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton

from ..automation.api.machine_status import set_machine_availability
from .machine_status_format import machine_slots


class _AvailabilityWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)


class MachineAvailabilityControl(QGroupBox):
    changed = Signal()

    def __init__(self, parent=None, *, write=set_machine_availability):
        super().__init__("机器可用性", parent)
        self.write = write
        self.machines = []
        self._lock = Lock()
        self.worker = _AvailabilityWorker(self)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.target = QComboBox()
        self.availability = QComboBox()
        self.availability.addItem("自动判断", "auto")
        self.availability.addItem("手工设为可用", "available")
        self.availability.addItem("手工设为不可用", "unavailable")
        self.apply_button = QPushButton("应用")
        self.apply_button.clicked.connect(self.apply)
        self.status = QLabel("默认可用；任务下发后没有反馈会自动判为不可用。")
        self.status.setWordWrap(True)
        layout = QHBoxLayout(self)
        layout.addWidget(self.target)
        layout.addWidget(self.availability)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.status, 1)
        self.target.currentIndexChanged.connect(self._sync)

    def set_data(self, machines):
        selected = self.target.currentData()
        self.machines = [
            item for item in machine_slots(machines)
            if item is not None and item.get("machine_id")
        ]
        self.target.blockSignals(True)
        self.target.clear()
        for machine in self.machines:
            self.target.addItem(machine["machine_name"], machine["machine_id"])
        index = self.target.findData(selected)
        self.target.setCurrentIndex(index if index >= 0 else 0)
        self.target.blockSignals(False)
        self.apply_button.setEnabled(bool(self.machines))
        self._sync()

    def _sync(self):
        index = self.target.currentIndex()
        if not 0 <= index < len(self.machines):
            return
        value = str(self.machines[index].get("availability_override") or "auto")
        option = self.availability.findData(value)
        self.availability.setCurrentIndex(max(0, option))

    def apply(self):
        machine_id = self.target.currentData()
        if not machine_id or not self._lock.acquire(blocking=False):
            return
        self.apply_button.setEnabled(False)
        self.status.setText("正在保存机器可用性…")
        Thread(
            target=self._write, args=(machine_id, self.availability.currentData()),
            daemon=True, name="machine-availability",
        ).start()

    def _write(self, machine_id, availability):
        try:
            self.worker.completed.emit(self.write(machine_id, availability))
        except Exception as error:
            self.worker.failed.emit(str(error))
        finally:
            self._lock.release()

    def _completed(self, _machine):
        self.apply_button.setEnabled(True)
        self.status.setText("已保存；自动判断会在机器重新反馈后恢复可用。")
        self.changed.emit()

    def _failed(self, message):
        self.apply_button.setEnabled(True)
        self.status.setText(f"保存失败：{message}")
