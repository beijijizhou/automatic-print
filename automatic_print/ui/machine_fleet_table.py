"""One-row projection of PrintExp hardware and AutomaticPrint software."""

from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QProgressBar, QTableWidget,
    QTableWidgetItem,
)

from ..batch_ui.platform.remote.queue import machine_workload
from .fleet_update_support import update_state
from .machine_status_format import (
    feedback_text, machine_display_name, machine_slots, remaining_text,
    status_text,
)


SOFTWARE_COLUMNS = (6, 7, 8)


def create_machine_fleet_table(parent=None, *, rows=11):
    table = QTableWidget(rows, 9, parent)
    table.setHorizontalHeaderLabels((
        "机位", "机器｜PrintExp", "机器｜当前 PRN", "机器｜进度",
        "机器｜剩余时间", "机器｜状态时间", "软件｜AutomaticPrint",
        "软件｜版本", "软件｜任务与更新",
    ))
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(42)
    table.setMinimumHeight(420)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.Stretch)
    header.setSectionResizeMode(8, QHeaderView.Stretch)
    return table


def set_software_columns_visible(table, visible):
    for column in SOFTWARE_COLUMNS:
        table.setColumnHidden(column, not visible)


def populate_machine_fleet_table(table, machines, commands, *, target=None, rows=11):
    slots = machine_slots(machines, rows)
    table.setRowCount(rows)
    for row, machine in enumerate(slots):
        if machine is None:
            _fill_pending(table, row)
        else:
            _fill_machine(table, row, machine, commands, target)
    return slots


def _fill_machine(table, row, machine, commands, target):
    workload = machine_workload(machine, commands)
    version_state = _version_state(machine, commands, target)
    values = (
        machine_display_name(machine),
        status_text(machine),
        machine.get("batch_name") or machine.get("batch_id") or "—",
        "",
        remaining_text(machine.get("remaining_seconds"), machine.get("state")),
        feedback_text(machine.get("feedback_age_seconds",
                                  machine.get("heartbeat_age_seconds"))),
        _software_status(machine),
        machine.get("app_version") or "—",
        _software_work(machine, workload, version_state),
    )
    for column, value in enumerate(values):
        item = QTableWidgetItem(str(value))
        if column == 8:
            item.setToolTip(str(value))
        table.setItem(row, column, item)
    progress = QProgressBar()
    value = machine.get("progress_percent")
    if value is None:
        progress.setRange(0, 0)
        progress.setFormat("未知")
    else:
        progress.setRange(0, 100)
        progress.setValue(max(0, min(100, int(value))))
        progress.setFormat("%p%")
    table.setCellWidget(row, 3, progress)


def _fill_pending(table, row):
    values = (f"M{row + 1}", "待接入", "—", "", "—", "—", "未接入", "—", "—")
    for column, value in enumerate(values):
        table.setItem(row, column, QTableWidgetItem(value))
    table.removeCellWidget(row, 3)


def _software_status(machine):
    if machine.get("identity_conflict"):
        return "机器号冲突"
    return "在线" if machine.get("agent_online") else "未响应"


def _software_work(machine, workload, version_state):
    parts = []
    if version_state:
        parts.append(version_state)
    if machine.get("identity_conflict"):
        parts.append("禁止远程操作")
    if workload["active_task"] != "无":
        parts.append(f"处理中：{workload['active_task']}")
    if workload["next_task"] != "无":
        parts.append(f"下一项：{workload['next_task']}")
    return "；".join(parts) or "空闲"


def _version_state(machine, commands, target):
    if target is None:
        return ""
    return update_state(
        machine, commands, target.version, target.revision,
        target.command_protocol, target.command_capabilities,
    )
