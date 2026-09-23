"""Project machine heartbeats and remote commands into one dispatch summary."""

import re

from ...ui.machine_status_format import remaining_text, status_text


ACTIVE_STATUSES = {"claimed", "running"}


def selected_batch_details(records, batch_numbers):
    """Keep the platform's authoritative item/piece counts with a command."""
    selected = set(map(str, batch_numbers))
    return [
        {
            "batch_number": str(record.batch_number),
            "item_count": max(0, int(record.item_count or 0)),
            "piece_count": max(0, int(record.piece_count or 0)),
        }
        for record in records
        if str(getattr(record, "batch_number", "")) in selected
    ]


def selection_text(details, batch_numbers):
    return _counts_text(details, len(batch_numbers))


def machine_workload(machine, commands):
    machine_id = str(machine.get("machine_id") or "")
    jobs = [
        command for command in commands
        if str(command.get("target_machine_id") or "") == machine_id
        and command.get("action") == "download_layout"
    ]
    active = sorted(
        (item for item in jobs if item.get("status") in ACTIVE_STATUSES),
        key=lambda item: str(item.get("created_at") or ""),
    )
    queued = sorted(
        (item for item in jobs if item.get("status") == "queued"),
        key=lambda item: str(item.get("created_at") or ""),
    )
    current_print = _current_print_text(machine)
    active_text = _command_text(active[0]) if active else "无"
    next_text = _command_text(queued[0]) if queued else "无"
    return {
        "machine": str(machine.get("machine_name") or machine_id),
        "status": status_text(machine),
        "current_print": current_print,
        "active_task": active_text,
        "next_task": next_text,
        "queued_count": len(queued),
    }


def compact_machine_text(machine, commands):
    view = machine_workload(machine, commands)
    current = view["current_print"]
    following = view["next_task"]
    if view["active_task"] != "无":
        current = f"后台处理中 {view['active_task']}；打印 {current}"
    return f"{view['machine']} · 当前 {current} · 接下来 {following}"


def workload_detail(machine, commands):
    view = machine_workload(machine, commands)
    queued_suffix = f"（队列共 {view['queued_count']} 条）" if view["queued_count"] else ""
    return (
        f"机器状态：{view['status']}\n"
        f"当前打印：{view['current_print']}\n"
        f"后台处理中：{view['active_task']}\n"
        f"接下来：{view['next_task']}{queued_suffix}"
    )


def _current_print_text(machine):
    name = str(machine.get("batch_name") or machine.get("batch_id") or "").strip()
    if not name:
        return "无"
    batch_info = machine.get("batch_info") or {}
    pieces = _nonnegative_int(batch_info.get("piece_count"))
    if pieces is None:
        pieces = _pieces_from_name(name)
    count = f" · {pieces}件" if pieces is not None else " · 件数未知"
    progress = machine.get("progress_percent")
    progress_text = f" · {int(progress)}%" if progress is not None else ""
    remaining = remaining_text(machine.get("remaining_seconds"), machine.get("state"))
    remaining_text_value = f" · 剩余{remaining}" if remaining != "—" else ""
    return f"{name}{count}{progress_text}{remaining_text_value}"


def _command_text(command):
    payload = command.get("payload") or {}
    batches = [str(value) for value in payload.get("batch_numbers") or []]
    platform = str(payload.get("platform") or "—")
    counts = _counts_text(payload.get("batch_details") or [], len(batches))
    batch_text = "、".join(batches[:2])
    if len(batches) > 2:
        batch_text += f"等{len(batches)}批"
    return f"{platform} · {batch_text or '批次未知'} · {counts}"


def _counts_text(details, fallback_batches):
    valid = [item for item in details if isinstance(item, dict)]
    items = sum(_nonnegative_int(item.get("item_count")) or 0 for item in valid)
    pieces = sum(_nonnegative_int(item.get("piece_count")) or 0 for item in valid)
    batches = len(valid) or int(fallback_batches)
    if not valid:
        return f"{batches}批 · 件数未知"
    return f"{batches}批 · {items}项目 · {pieces}件"


def _pieces_from_name(name):
    match = re.search(r"(?<!\d)(\d+)件", name)
    return int(match.group(1)) if match else None


def _nonnegative_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None
