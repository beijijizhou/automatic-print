"""Remote download/layout command requests over the restricted Edge Function."""

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
    return _call(
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


def submit_printer_action(target_machine_id, action, *, expires_minutes=2, timeout=8):
    if action not in {"pause_print", "clean_resume"}:
        raise ValueError("不支持的打印机控制指令。")
    return _call(
        {
            "action": "send_control",
            "command_action": action,
            "machine_id": machine_id(),
            "machine_name": machine_name(),
            "target_machine_id": str(target_machine_id),
            "expires_minutes": int(expires_minutes),
            "payload": {},
        },
        timeout=timeout,
    )["command"]


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
