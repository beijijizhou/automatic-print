"""One-shot target acknowledgement before a production command is sent."""

from time import monotonic, sleep

from .commands import get_command, submit_probe


class MachinePreflightError(RuntimeError):
    pass


def preflight_machine(
    target_machine_id,
    expected_machine_name,
    *,
    required_capability=None,
    deadline_seconds=12,
    poll_seconds=0.5,
    submit=submit_probe,
    fetch=get_command,
    clock=monotonic,
    wait=sleep,
):
    command = submit(str(target_machine_id))
    command_id = str(command.get("id") or "")
    if not command_id:
        raise MachinePreflightError("机器探测请求没有返回指令编号。")
    deadline = clock() + float(deadline_seconds)
    while clock() < deadline:
        current = fetch(command_id)
        status = str(current.get("status") or "")
        if status == "succeeded":
            return _validate_result(
                current.get("result") or {}, target_machine_id, expected_machine_name,
                required_capability,
            )
        if status in {"failed", "cancelled", "expired"}:
            reason = current.get("error_message") or current.get("phase") or status
            raise MachinePreflightError(f"目标机没有通过检测：{reason}")
        wait(float(poll_seconds))
    raise MachinePreflightError(
        f"{expected_machine_name} 在 {int(deadline_seconds)} 秒内没有回应；未发送生产任务。"
    )


def _validate_result(result, target_machine_id, expected_machine_name, required_capability=None):
    if str(result.get("machine_id") or "") != str(target_machine_id):
        raise MachinePreflightError("回应机器与选择的目标机器不一致。")
    actual_name = str(result.get("machine_name") or "").upper()
    if actual_name != str(expected_machine_name).upper():
        raise MachinePreflightError(
            f"回应机器号为 {actual_name or '未知'}，不是 {expected_machine_name}。"
        )
    if result.get("source_online") is not True:
        raise MachinePreflightError("目标机已回应，但 PrintExp 没有连接。")
    if not str(result.get("app_version") or "").strip():
        raise MachinePreflightError("目标机没有返回 AutomaticPrint 版本。")
    if required_capability and required_capability not in set(result.get("capabilities") or []):
        raise MachinePreflightError(
            f"目标机已回应，但当前版本不支持 {required_capability}功能。"
        )
    return dict(result)
