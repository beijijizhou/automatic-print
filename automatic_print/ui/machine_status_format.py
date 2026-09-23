"""Short display labels for the PrintExp fleet table."""

import re


def status_text(machine):
    if machine.get("identity_conflict"):
        return "机器号冲突"
    if not machine.get("agent_online"):
        return "监控离线"
    if not machine.get("source_online"):
        return "PrintExp 离线"
    return {
        "running": "打印中",
        "idle": "空闲",
        "completed": "已完成",
        "failed": "异常",
        "stopped": "已停止",
    }.get(machine.get("state"), "未知")


def remaining_text(seconds, state):
    if seconds is None:
        return "估算中" if state == "running" else "—"
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes = (rest + 59) // 60
    return f"{hours}小时{minutes}分钟" if hours else f"{minutes}分钟"


def heartbeat_text(seconds):
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    return f"{seconds}秒前" if seconds < 60 else f"{seconds // 60}分钟前"


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
        and machine.get("agent_online")
        and (not require_source or machine.get("source_online"))
    ]


def _freshness_key(machine):
    age = machine.get("heartbeat_age_seconds")
    return float("inf") if age is None else max(0, float(age))
