"""Short display labels for the PrintExp fleet table."""

import re

from ..automation.api.printerexp.state_machine import printer_state_label


def status_text(machine):
    if machine.get("identity_conflict"):
        return "机器号冲突"
    available = machine.get("available")
    if available is None:
        available = machine.get("agent_online")
    if not available:
        return "无反馈，不可用"
    if not machine.get("source_online"):
        return "PrintExp 离线"
    printer_state = machine_printer_state(machine)
    if printer_state:
        if printer_state == "ready" and (
            machine.get("batch_info") or {}
        ).get("task_name_verified") is False:
            return "待打印（待复核）"
        return printer_state_label(printer_state)
    return {
        "running": "打印中",
        "idle": "空闲",
        "completed": "已完成",
        "failed": "异常",
        "stopped": "已停止",
    }.get(machine.get("state"), "未知")


def machine_printer_state(machine):
    value = str((machine.get("batch_info") or {}).get("printer_state") or "")
    if value:
        return value
    return "printing" if machine.get("state") == "running" else ""


def remaining_text(seconds, state):
    if seconds is None:
        return "估算中" if state == "running" else "—"
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes = (rest + 59) // 60
    return f"{hours}小时{minutes}分钟" if hours else f"{minutes}分钟"


def feedback_text(seconds):
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    return f"{seconds}秒前" if seconds < 60 else f"{seconds // 60}分钟前"


heartbeat_text = feedback_text


def machine_slots(machines, count=11):
    slots = [None] * count
    grouped = {}
    for machine in machines:
        match = re.fullmatch(
            r"M(?:[1-9]|1[01])", str(machine.get("machine_name") or "").upper()
        )
        if not match:
            continue
        index = int(match.group()[1:]) - 1
        if 0 <= index < count:
            grouped.setdefault(index, []).append(machine)
    for index, candidates in grouped.items():
        selected = min(candidates, key=_freshness_key)
        selected = {**selected, "machine_name": f"M{index + 1}"}
        if len(candidates) > 1:
            selected.update(identity_conflict=True, conflict_count=len(candidates))
        slots[index] = selected
    return slots


def actionable_machines(machines, *, require_source=False, count=11):
    return [
        machine for machine in machine_slots(machines, count)
        if machine is not None
        and not machine.get("identity_conflict")
        and machine.get("available", machine.get("agent_online", True))
        and (not require_source or machine.get("source_online"))
    ]


def _freshness_key(machine):
    age = machine.get("feedback_age_seconds", machine.get("heartbeat_age_seconds"))
    return float("inf") if age is None else max(0, float(age))
