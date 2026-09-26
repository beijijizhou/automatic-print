"""Remote download/layout command requests over the restricted Edge Function."""

from ....runtime.monitoring.control import notify_machine
from ....runtime.monitoring.cloud_wake import notify_machine_via_cloud
from .client import _call
from .identity import machine_id, machine_name


def submit_command(
    target_machine_id,
    platform,
    batch_numbers,
    layout_settings,
    *,
    batch_details=None,
    generate_prn=True,
    expires_minutes=30,
    timeout=8,
):
    command = _call(
        {
            "action": "enqueue_command",
            "machine_id": machine_id(),
            "machine_name": machine_name(),
            "target_machine_id": str(target_machine_id),
            "expires_minutes": int(expires_minutes),
            "payload": {
                "platform": str(platform),
                "batch_numbers": list(batch_numbers),
                "batch_details": list(batch_details or []),
                "layout_settings": dict(layout_settings),
                "generate_prn": bool(generate_prn),
            },
        },
        timeout=timeout,
    )["command"]
    return _notify_target(command, target_machine_id)


def submit_printer_action(
    target_machine_id, action, *, expected_batch_name="", expires_minutes=2, timeout=8,
):
    if action not in {"start_print", "pause_print", "clean_resume"}:
        raise ValueError("不支持的打印机控制指令。")
    payload = {}
    if action == "start_print":
        expected_batch_name = str(expected_batch_name).strip()
        if not expected_batch_name:
            raise ValueError("开始打印前必须指定批次文件名。")
        payload["expected_batch_name"] = expected_batch_name
    command = _call(
        {
            "action": "send_control",
            "command_action": action,
            "machine_id": machine_id(),
            "machine_name": machine_name(),
            "target_machine_id": str(target_machine_id),
            "expires_minutes": int(expires_minutes),
            "payload": payload,
        },
        timeout=timeout,
    )["command"]
    return _notify_target(command, target_machine_id)


def submit_application_launch(target_machine_id, *, expires_minutes=2, timeout=8):
    command = _call(
        {
            "action": "send_control",
            "command_action": "launch_app",
            "machine_id": machine_id(),
            "machine_name": machine_name(),
            "target_machine_id": str(target_machine_id),
            "expires_minutes": int(expires_minutes),
            "payload": {},
        },
        timeout=timeout,
    )["command"]
    return _notify_target(command, target_machine_id)


def submit_probe(target_machine_id, *, expires_minutes=1, timeout=8, realtime_only=False):
    command = _call(
        {
            "action": "send_control",
            "command_action": "probe",
            "machine_id": machine_id(),
            "machine_name": machine_name(),
            "target_machine_id": str(target_machine_id),
            "expires_minutes": int(expires_minutes),
            "payload": {},
        },
        timeout=timeout,
    )["command"]
    return _notify_target(command, target_machine_id, lan_first=not realtime_only)


def submit_history_request(target_machine_id, *, limit=500, days=2, expires_minutes=1, timeout=8):
    command = _call(
        {
            "action": "send_control",
            "command_action": "probe",
            "machine_id": machine_id(),
            "machine_name": machine_name(),
            "target_machine_id": str(target_machine_id),
            "expires_minutes": int(expires_minutes),
            "payload": {
                "request": "printer_history",
                "limit": max(1, min(int(limit), 500)),
                "days": max(1, min(int(days), 31)),
            },
        },
        timeout=timeout,
    )["command"]
    return _notify_target(command, target_machine_id)


def submit_source_update(
    target_machine_id, target_revision, target_version, *, expires_minutes=1440, timeout=8,
):
    command = _call(
        {
            "action": "enqueue_update",
            "machine_id": machine_id(),
            "machine_name": machine_name(),
            "target_machine_id": str(target_machine_id),
            "expires_minutes": int(expires_minutes),
            "payload": {
                "target_revision": str(target_revision),
                "target_version": str(target_version),
            },
        },
        timeout=timeout,
    )["command"]
    return _notify_target(command, target_machine_id)


def _notify_target(command, target_machine_id, *, lan_first=True):
    command_id = str(command.get("id") or "")
    try:
        try:
            acknowledged = lan_first and notify_machine(target_machine_id, command_id=command_id)
        except OSError:
            acknowledged = False
        if acknowledged:
            return command
        notify_machine_via_cloud(target_machine_id, command_id=command_id)
    except OSError as error:
        if command_id:
            try:
                cancel_command(command_id)
            except Exception:
                pass
        raise RuntimeError(f"无法通知目标机领取任务：{error}") from error
    return command


def list_commands(*, timeout=8):
    return _call({"action": "list_commands"}, timeout=timeout)["commands"]


def claim_command(*, timeout=5):
    return _call(
        {"action": "claim_command", "machine_id": machine_id()}, timeout=timeout
    )["command"]


def claim_control(*, timeout=2):
    return _call(
        {"action": "claim_control", "machine_id": machine_id()}, timeout=timeout
    )["command"]


def get_command(command_id, *, timeout=8):
    return _call(
        {
            "action": "get_command",
            "machine_id": machine_id(),
            "command_id": str(command_id),
        },
        timeout=timeout,
    )["command"]


def update_command(
    command_id,
    status,
    *,
    phase="",
    progress_percent=None,
    result=None,
    error_message=None,
    timeout=8,
):
    return _call(
        {
            "action": "update_command",
            "machine_id": machine_id(),
            "command_id": str(command_id),
            "status": str(status),
            "phase": str(phase),
            "progress_percent": progress_percent,
            "result": result or {},
            "error_message": error_message,
        },
        timeout=timeout,
    )["command"]


def cancel_command(command_id, *, timeout=8):
    return _call(
        {"action": "cancel_command", "command_id": str(command_id)},
        timeout=timeout,
    )["command"]


def consume_command_result(command_id, *, timeout=8):
    return _call(
        {
            "action": "consume_command_result",
            "machine_id": machine_id(),
            "command_id": str(command_id),
        },
        timeout=timeout,
    )["result"]
