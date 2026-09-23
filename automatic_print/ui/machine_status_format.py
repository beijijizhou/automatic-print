"""Short display labels for the PrintExp fleet table."""


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
