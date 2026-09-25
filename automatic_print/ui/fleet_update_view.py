"""Pure display text and target-state helpers for fleet version management."""

from .fleet_update_support import update_state


def release_notes_text(target):
    notes = tuple(getattr(target, "release_notes", ()) or ())
    text = "\n".join(f"• {item}" for item in notes) if notes else "当前版本没有提供说明。"
    return f"版本说明：\n{text}"


def target_state(machine, commands, target):
    return update_state(
        machine, commands, target.version,
        getattr(target, "revision", ""),
        getattr(target, "command_protocol", 0),
        getattr(target, "command_capabilities", ()),
    )


def switch_confirmation_text(target, targets):
    names = "\n".join(
        f"{item.get('machine_name') or '未知机器'}："
        f"{item.get('app_version') or '未知'} → {target.version}"
        for item in targets
    )
    features = (
        "本次功能：\n" + "\n".join(f"• {item}" for item in target.release_notes) + "\n\n"
        if target.release_notes else ""
    )
    return (
        f"将 {len(targets)} 台电脑切换到 {target.display_version}\n"
        f"提交：{target.revision}\n\n{names}\n\n{features}"
        "目标机若有已跟踪的本地代码修改会拒绝切换；"
        "生产任务不会被强制停止，完成后安全重启。"
    )
