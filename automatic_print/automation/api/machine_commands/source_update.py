"""Pinned source update execution for a claimed fleet command."""

import os
import subprocess

from ....updates.source import SourceUpdater


def execute_source_update(payload, progress):
    revision = str(payload.get("target_revision") or "").strip().lower()
    version = str(payload.get("target_version") or "").strip()
    progress(f"正在检查目标源码 {version or revision[:8]}", force=True)
    updater = SourceUpdater(progress=progress)
    info = updater.check(revision)
    if version and info.version != version:
        raise RuntimeError(
            f"目标提交版本为 {info.version}，与下发版本 {version} 不一致。"
        )
    if info.needs_update:
        updater.apply(info)
    return {
        "target_revision": info.target,
        "target_version": info.version,
        "updated": info.needs_update,
        "rollback": info.rollback,
        "operation": "rollback" if info.rollback else "update",
        "restart_pending": True,
    }


def schedule_monitor_restart():
    """Reload the elevated monitor after the command receipt is committed."""
    if os.name != "nt":
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    script = (
        "Start-Sleep -Seconds 2; "
        "schtasks.exe /End /TN AutomaticPrintMonitor 2>$null; "
        "schtasks.exe /Run /TN AutomaticPrintMonitor 2>$null"
    )
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
