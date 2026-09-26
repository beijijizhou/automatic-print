"""Version feature-probe decisions shared by the fleet update UI."""

ACTIVE = {"queued", "claimed", "running"}


def verification_needed(machine, commands, target):
    if not target or not int(getattr(target, "command_protocol", 0) or 0):
        return False
    if str(machine.get("app_version") or "") != str(target.version):
        return False
    return verification_state(
        machine, commands, target.version, target.revision,
        target.command_protocol, target.command_capabilities,
    ) == "版本已回报，等待功能检测"


def automatic_verification_needed(machine, commands, target):
    """Probe after a reported source update even when developer tools are hidden."""
    if verification_needed(machine, commands, target):
        return True
    machine_id = str(machine.get("machine_id") or "")
    version = str(machine.get("app_version") or "")
    if not machine_id or not version:
        return False
    updates = [
        item for item in commands
        if item.get("action") == "source_update"
        and str(item.get("target_machine_id") or "") == machine_id
        and str(item.get("status") or "") == "succeeded"
        and str((item.get("payload") or {}).get("target_version") or "") == version
    ]
    if not updates:
        return False
    latest_update = max(updates, key=lambda item: str(item.get("created_at") or ""))
    update_time = str(latest_update.get("created_at") or "")
    for command in commands:
        if (command.get("action") != "probe"
                or str(command.get("target_machine_id") or "") != machine_id):
            continue
        if str(command.get("created_at") or "") < update_time:
            continue
        if str(command.get("status") or "") in ACTIVE:
            return False
        result = command.get("result") or {}
        if (str(command.get("status") or "") == "succeeded"
                and str(result.get("app_version") or "") == version):
            return False
    return True


def verification_state(
    machine, commands, target_version, target_revision,
    target_protocol, target_capabilities,
):
    machine_id = str(machine.get("machine_id") or "")
    probes = [
        item for item in commands
        if item.get("action") == "probe"
        and str(item.get("target_machine_id") or "") == machine_id
    ]
    probes.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    target_revision = str(target_revision or "").lower()
    for command in probes:
        status = str(command.get("status") or "")
        result = command.get("result") or {}
        if status in ACTIVE:
            return "版本已回报，正在验证功能"
        if str(result.get("app_version") or "") != str(target_version):
            continue
        revision = str(result.get("source_revision") or "").lower()
        if target_revision and revision != target_revision:
            return "版本号一致，但提交号不一致"
        if int(result.get("command_protocol") or 0) < int(target_protocol or 0):
            return "版本号一致，但指令协议未加载"
        actual = set(result.get("capabilities") or [])
        missing = sorted(set(target_capabilities or ()) - actual)
        if missing:
            return "版本号一致，但缺少功能：" + "、".join(missing)
        return "功能已确认"
    return "版本已回报，等待功能检测"
