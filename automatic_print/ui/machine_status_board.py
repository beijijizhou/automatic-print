"""Fleet view for PrintExp status and remote production commands."""

from threading import Lock, Thread

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..automation.api.machine_status import list_commands, list_machines
from ..automation.api.machine_status.identity import machine_id
from .machine_command_ui import RemoteCommandPanel
from .printer_control_ui import PrinterControlPanel
from .machine_status_format import machine_slots, mark_local_machine
from .machine_fleet_table import (
    create_machine_fleet_table, populate_machine_fleet_table,
    set_software_columns_visible,
)
from .machine_availability import MachineAvailabilityControl
from .machine_status_layout import build_machine_status_layout
from .fleet_update import FleetUpdatePanel
from .fleet_update_action import fail_pending_latest_update, resume_pending_latest_update
from .machine_signal_test import install_machine_signal_control
from .machine_registration import MachineRegistrationPanel
from .printer_history import PrinterHistoryPanel
from .software_launch import SoftwareLaunchPanel


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
            dashboard = self.fetch()
        except Exception as error:
            try:
                self.failed.emit(str(error))
            except RuntimeError:
                pass  # The page was closed while the background read finished.
        else:
            try:
                self.loaded.emit(dashboard)
            except RuntimeError:
                pass  # The page was closed while the background read finished.
        finally:
            self._lock.release()


class MachineStatusPage(QWidget):
    def __init__(self, parent=None, fetch=load_dashboard, signal_tester=None):
        super().__init__(parent)
        self._active = False
        self.loader = MachineStatusLoader(fetch, self)
        self.loader.loaded.connect(self.apply_dashboard)
        self.loader.failed.connect(self.show_error)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(5_000)
        self.update_timer.timeout.connect(self.refresh)
        title = QLabel("机器与软件管理")
        title.setProperty("heading", True)
        description = QLabel(
            "每行左侧显示 PrintExp 机器事实；开发者模式下，右侧同时显示 "
            "AutomaticPrint 软件、版本和远程任务状态。"
        )
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
        overview = QGroupBox("11 台机器总览")
        overview_layout = QVBoxLayout(overview)
        overview_layout.addLayout(header)
        overview_layout.addWidget(self.message)
        self.signal_control = install_machine_signal_control(self, signal_tester)

        self.table = create_machine_fleet_table(self, rows=EXPECTED_MACHINES)
        self.apply_machines([])
        self.command_panel = RemoteCommandPanel(parent or self.window(), self)
        self.command_panel.command_submitted.connect(self.refresh)
        self.control_panel = PrinterControlPanel(self)
        self.control_panel.command_submitted.connect(self.refresh)
        self.availability_control = MachineAvailabilityControl(self)
        self.availability_control.changed.connect(self.refresh)
        self.software_launch_panel = SoftwareLaunchPanel(self)
        self.software_launch_panel.command_submitted.connect(self.refresh)
        self.update_panel = FleetUpdatePanel(self, auto_load=False)
        self.update_panel.set_compact(True)
        self.update_panel.loader.completed.connect(
            lambda _versions: resume_pending_latest_update(self)
        )
        self.update_panel.loader.failed.connect(
            lambda error: fail_pending_latest_update(self, error)
        )
        self.update_panel.versions.currentIndexChanged.connect(
            self._refresh_fleet_table
        )
        self.update_panel.commands_submitted.connect(self._track_updates)
        self.update_panel.commands_submitted.connect(self._show_update_feedback)
        self.history_panel = PrinterHistoryPanel(self)
        self.registration_panel = MachineRegistrationPanel(self)
        self.registration_panel.registered.connect(self._apply_registered_machine)

        build_machine_status_layout(self, title, description, overview)
        self.set_developer_mode(
            bool(getattr(self.window(), "developer_mode_enabled", False))
        )

    def _apply_registered_machine(self, name):
        window = self.window()
        for combo in (
            getattr(getattr(window, "label_settings", None), "machine", None),
            getattr(getattr(getattr(window, "automation_home", None),
                            "label_quick_panel", None), "machine", None),
        ):
            if combo is not None:
                index = combo.findData(name)
                if index >= 0:
                    combo.setCurrentIndex(index)
        preferences = getattr(window, "preferences", None)
        if preferences is not None:
            preferences.setValue("layout/machine_number", name)
            preferences.sync()
        self.refresh()

    def set_active(self, active):
        self._active = bool(active)
        if self._active:
            self.registration_panel.refresh()
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
        self.signal_control.set_machines(machines)
        self.update_panel.set_data(machines, commands)
        self.apply_machines(machines, commands)
        self.control_panel.set_data(machines)
        self.command_panel.set_data(machines, commands)
        self.availability_control.set_data(machines)
        self.software_launch_panel.set_data(machines)
        self.history_panel.set_data(machines)
        has_active_commands = any(
            command.get("status") in {"claimed", "running"}
            for command in commands
        )
        if self.update_panel.has_active_updates() or has_active_commands:
            self.update_timer.start()
        else:
            self.update_timer.stop()

    def _track_updates(self):
        self.update_timer.start()
        self.refresh()

    def _show_update_feedback(self):
        self.signal_update_button.setEnabled(True)
        self.signal_result.setText(self.update_panel.summary.text())

    def set_developer_mode(self, enabled):
        enabled = bool(enabled)
        set_software_columns_visible(self.table, enabled)
        self.signal_group.setVisible(enabled)
        self.signal_button.setVisible(enabled)
        self.signal_update_button.setVisible(enabled)
        self.signal_result.setVisible(enabled)
        self.update_panel.setVisible(enabled)
        self.software_launch_panel.setVisible(enabled)
        target = self.update_panel.target()
        if enabled and not str(getattr(target, "revision", "") or ""):
            self.update_panel.load_versions()

    def apply_machines(self, machines, commands=None):
        machines = [item for item in machines if isinstance(item, dict)]
        commands = [item for item in (commands or []) if isinstance(item, dict)]
        self._machines, self._commands = machines, commands
        slots = machine_slots(machines, EXPECTED_MACHINES)
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
            "左侧为 PrintExp 机器状态；AutomaticPrint 软件信息仅在开发者模式显示。"
        )
        self.refresh_button.setEnabled(True)
        populate_machine_fleet_table(
            self.table, machines, commands,
            target=(self.update_panel.target()
                    if hasattr(self, "update_panel") else None),
            rows=EXPECTED_MACHINES,
        )

    def _refresh_fleet_table(self, _index=None):
        if hasattr(self, "_machines"):
            populate_machine_fleet_table(
                self.table, self._machines, self._commands,
                target=self.update_panel.target(), rows=EXPECTED_MACHINES,
            )

    def show_error(self, message):
        self.refresh_button.setEnabled(True)
        self.message.setText(f"读取失败：{message}；已保留上一次显示结果，可手动重试。")

def install_machine_status_tab(window, tabs):
    page = MachineStatusPage(window)
    index = tabs.addTab(page, "机器与软件")
    tabs.setTabToolTip(index, "逐行查看 11 台 PrintExp 机器及 AutomaticPrint 软件状态。")
    window.machine_status_page = page
    window.machine_status_tab_index = index
    tabs.currentChanged.connect(lambda current: page.set_active(current == index))
    window.developer_mode_checkbox.toggled.connect(page.set_developer_mode)
    page.set_developer_mode(window.developer_mode_checkbox.isChecked())
    page.set_active(tabs.currentIndex() == index)
    return page
