"""Short display labels for the PrintExp fleet table."""

import re


def status_text(machine):
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
    unmatched = []
    for machine in machines:
        match = re.fullmatch(
            r"M(?:[1-9]|1[01])", str(machine.get("machine_name") or "").upper()
        )
        index = int(match.group()[1:]) - 1 if match else -1
        if 0 <= index < count and slots[index] is None:
            slots[index] = machine
        else:
            unmatched.append(machine)
    for machine in unmatched:
        try:
            slots[slots.index(None)] = machine
        except ValueError:
            break
    return slots
