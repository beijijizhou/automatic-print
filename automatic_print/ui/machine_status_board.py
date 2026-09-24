"""Fleet view for PrintExp status and remote production commands."""

from threading import Lock, Thread

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..automation.api.machine_status import list_commands, list_machines
from ..automation.api.machine_status.identity import machine_id
from ..batch_ui.platform.remote.queue import machine_workload
from .machine_command_ui import RemoteCommandPanel
from .printer_control_ui import PrinterControlPanel
from .machine_status_format import (
    feedback_text, machine_display_name, machine_slots, mark_local_machine,
    remaining_text, status_text,
)
from .machine_availability import MachineAvailabilityControl
from .machine_status_layout import build_machine_status_layout
from .fleet_update import FleetUpdatePanel


EXPECTED_MACHINES = 11


def load_dashboard():
    return {
        "machines": mark_local_machine(list_machines(), machine_id()),
        "commands": list_commands(),
    }


class MachineStatusLoader(QObject):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, fetch=list_machines, parent=None):
        super().__init__(parent)
        self.fetch = fetch
        self._lock = Lock()

    def refresh(self):
        if not self._lock.acquire(blocking=False):
            return False
        Thread(target=self._run, daemon=True, name="machine-status-list").start()
        return True

    def _run(self):
        try:
            self.loaded.emit(self.fetch())
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self._lock.release()


class MachineStatusPage(QWidget):
    def __init__(self, parent=None, fetch=load_dashboard):
        super().__init__(parent)
        self._active = False
        self.loader = MachineStatusLoader(fetch, self)
        self.loader.loaded.connect(self.apply_dashboard)
        self.loader.failed.connect(self.show_error)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(5_000)
        self.update_timer.timeout.connect(self.refresh)
        title = QLabel("PrintExp 打印机状态")
        title.setProperty("heading", True)
        description = QLabel("显示最近一次机器回执；发送任务前会现场查询指定机器的"
                             "PrintExp 状态，不发送周期心跳。")
        description.setWordWrap(True)
        self.summary = QLabel("已接入 0 / 11 · 在线 0 · 打印中 0")
        self.summary.setStyleSheet("font-size:16px;font-weight:700;color:#0f172a;")
        self.message = QLabel("打开本页后自动读取；未接入的机位会显示为待接入。")
        self.message.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.refresh_button = QPushButton("刷新打印机状态")
        self.refresh_button.clicked.connect(self.refresh)

        header = QHBoxLayout()
        header.addWidget(self.summary)
        header.addStretch()
        header.addWidget(self.refresh_button)
        overview = QGroupBox("11 台打印机总览")
        overview_layout = QVBoxLayout(overview)
        overview_layout.addLayout(header)
        overview_layout.addWidget(self.message)

        self.table = QTableWidget(EXPECTED_MACHINES, 9)
        self.table.setHorizontalHeaderLabels(
            (
                "打印机", "部门", "状态", "当前批次", "进度", "剩余时间",
                "最后反馈", "后台处理中", "下一任务",
            )
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setMinimumHeight(420)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.Stretch)
        header_view.setSectionResizeMode(8, QHeaderView.Stretch)
        self.apply_machines([])
        self.command_panel = RemoteCommandPanel(parent or self.window(), self)
        self.command_panel.command_submitted.connect(self.refresh)
        self.control_panel = PrinterControlPanel(self)
        self.control_panel.command_submitted.connect(self.refresh)
        self.availability_control = MachineAvailabilityControl(self)
        self.availability_control.changed.connect(self.refresh)
        self.update_panel = FleetUpdatePanel(self)
        self.update_panel.commands_submitted.connect(self._track_updates)

        build_machine_status_layout(self, title, description, overview)

    def set_active(self, active):
        self._active = bool(active)
        if self._active:
            self.refresh()

    def refresh(self):
        if self.loader.refresh():
            self.refresh_button.setEnabled(False)
            self.message.setText("正在读取 Supabase 中的 PrintExp 状态…")

    def apply_dashboard(self, dashboard):
        if isinstance(dashboard, list):
            dashboard = {"machines": dashboard, "commands": []}
        machines = dashboard.get("machines") or []
        commands = dashboard.get("commands") or []
        self.apply_machines(machines, commands)
        self.control_panel.set_data(machines)
        self.command_panel.set_data(machines, commands)
        self.availability_control.set_data(machines)
        self.update_panel.set_data(machines, commands)
        if self.update_panel.has_active_updates():
            self.update_timer.start()
        else:
            self.update_timer.stop()

    def _track_updates(self):
        self.update_timer.start()
        self.refresh()

    def apply_machines(self, machines, commands=None):
        machines = [item for item in machines if isinstance(item, dict)]
        commands = [item for item in (commands or []) if isinstance(item, dict)]
        slots = machine_slots(machines, EXPECTED_MACHINES)
        self.table.setRowCount(EXPECTED_MACHINES)
        connected = [item for item in slots if item is not None]
        conflicts = sum(bool(item.get("identity_conflict")) for item in connected)
        online = sum(bool(item.get("available", item.get("online")))
                     and not item.get("identity_conflict") for item in connected)
        running = sum(
            item.get("state") == "running" and item.get("available", item.get("online"))
            and not item.get("identity_conflict") for item in connected
        )
        conflict_text = f" · 机器号冲突 {conflicts}" if conflicts else ""
        self.summary.setText(
            f"已接入 {len(connected)} / {EXPECTED_MACHINES} · 可用 {online}"
            f" · 打印中 {running}{conflict_text}"
        )
        self.message.setText(
            "仅显示排版设置中的 M1–M11；同号电脑会标记冲突并禁止远程控制。"
        )
        self.refresh_button.setEnabled(True)
        for row, machine in enumerate(slots):
            if machine is not None:
                self._fill_machine(row, machine, commands)
            else:
                self._fill_pending(row)

    def show_error(self, message):
        self.refresh_button.setEnabled(True)
        self.message.setText(f"读取失败：{message}；已保留上一次显示结果，可手动重试。")

    def _fill_machine(self, row, machine, commands):
        workload = machine_workload(machine, commands)
        values = (
            machine_display_name(machine),
            machine.get("department") or "—",
            status_text(machine),
            machine.get("batch_name") or machine.get("batch_id") or "—",
            "",
            remaining_text(machine.get("remaining_seconds"), machine.get("state")),
            feedback_text(machine.get("feedback_age_seconds", machine.get("heartbeat_age_seconds"))),
            workload["active_task"],
            workload["next_task"],
        )
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(str(value)))
        progress = QProgressBar()
        value = machine.get("progress_percent")
        if value is None:
            progress.setRange(0, 0)
            progress.setFormat("未知")
        else:
            progress.setRange(0, 100)
            progress.setValue(max(0, min(100, int(value))))
            progress.setFormat("%p%")
        self.table.setCellWidget(row, 4, progress)

    def _fill_pending(self, row):
        values = (
            f"M{row + 1}", "—", "待接入", "—", "", "—", "—", "—", "—",
        )
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.removeCellWidget(row, 4)


def install_machine_status_tab(window, tabs):
    page = MachineStatusPage(window)
    index = tabs.addTab(page, "打印机状态")
    tabs.setTabToolTip(index, "查看 11 台 PrintExp 打印机的在线、批次、进度与剩余时间。")
    window.machine_status_page = page
    window.machine_status_tab_index = index
    tabs.currentChanged.connect(lambda current: page.set_active(current == index))
    page.set_active(tabs.currentIndex() == index)
    return page
