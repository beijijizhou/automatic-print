"""Human-confirmed, database-authoritative machine-slot registration."""

from threading import Lock, Thread

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout,
)

from ..automation.api.machine_status import get_machine_registration, register_machine
from ..automation.api.machine_status.identity import machine_id


class MachineRegistrationWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None, fetch=get_machine_registration, register=register_machine):
        super().__init__(parent)
        self.fetch = fetch
        self.register = register
        self.lock = Lock()

    def start(self, machine_name=None, replace=False):
        if not self.lock.acquire(blocking=False):
            return False
        Thread(
            target=self._run, args=(machine_name, replace), daemon=True,
            name="machine-registration",
        ).start()
        return True

    def _run(self, machine_name, replace):
        try:
            result = self.fetch() if machine_name is None else self.register(
                machine_name, replace=replace,
            )
        except Exception as error:
            try:
                self.failed.emit(str(error))
            except RuntimeError:
                pass
        else:
            try:
                self.completed.emit(result)
            except RuntimeError:
                pass
        finally:
            self.lock.release()


class MachineRegistrationPanel(QGroupBox):
    registered = Signal(str)

    def __init__(self, parent=None, worker=None, confirm=None):
        super().__init__("本机注册", parent)
        self.worker = worker or MachineRegistrationWorker(self)
        self.confirm = confirm or self._confirm
        self.registrations = []
        self.current = None
        self.status = QLabel(f"本机 ID：{machine_id()} · 正在查询数据库注册信息…")
        self.status.setWordWrap(True)
        self.machine = QComboBox()
        for number in range(1, 12):
            self.machine.addItem(f"M{number}", f"M{number}")
        self.button = QPushButton("注册本机")
        self.button.clicked.connect(self.request_registration)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("机器号"))
        controls.addWidget(self.machine)
        controls.addWidget(self.button)
        controls.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addLayout(controls)
        self.worker.completed.connect(self.apply_result)
        self.worker.failed.connect(self.show_error)

    def refresh(self):
        self.worker.start()

    def request_registration(self):
        name = self.machine.currentData()
        current_name = (self.current or {}).get("machine_name")
        if current_name == name:
            self.status.setText(f"本机已由数据库注册为 {name}，无需重复注册。")
            return
        occupant = next(
            (item for item in self.registrations if item.get("machine_name") == name), None,
        )
        replace = bool(occupant and occupant.get("machine_id") != machine_id())
        if not self.confirm(name, occupant, current_name):
            return
        self.button.setEnabled(False)
        self.status.setText(f"正在向数据库注册 {name}…")
        if not self.worker.start(name, replace=replace):
            self.button.setEnabled(True)

    def apply_result(self, result):
        self.button.setEnabled(True)
        registration = result.get("registration")
        if "registrations" in result:
            self.registrations = result.get("registrations") or []
            self.current = registration
        elif registration:
            self.current = registration
            self.registrations = [
                item for item in self.registrations
                if item.get("machine_id") != registration.get("machine_id")
                and item.get("machine_name") != registration.get("machine_name")
            ] + [registration]
        if not self.current:
            self.status.setText(f"本机 ID：{machine_id()} · 尚未注册，请人工选择 M1–M11。")
            return
        name = self.current["machine_name"]
        index = self.machine.findData(name)
        if index >= 0:
            self.machine.setCurrentIndex(index)
        replaced = result.get("replaced")
        suffix = "；旧电脑绑定已解除" if replaced else ""
        self.status.setText(f"数据库确认：本机是 {name}{suffix}。")
        self.registered.emit(name)

    def show_error(self, message):
        self.button.setEnabled(True)
        self.status.setText(f"注册失败：{message}")

    def _confirm(self, name, occupant, current_name):
        if occupant and occupant.get("machine_id") != machine_id():
            detail = (
                f"{name} 已注册到另一台电脑：\n{occupant.get('machine_id')}\n\n"
                "继续会解除旧电脑绑定，并以本机为准。是否确认换绑？"
            )
            title = "确认换绑机器号"
        else:
            previous = f"（当前为 {current_name}）" if current_name else ""
            detail = f"确认把本机注册为 {name}{previous}？\n数据库将作为机器号唯一依据。"
            title = "确认注册本机"
        return QMessageBox.question(self, title, detail) == QMessageBox.Yes
