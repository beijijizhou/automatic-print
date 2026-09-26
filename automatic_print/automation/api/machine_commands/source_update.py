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
        return False
    flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    )
    # Do not end the scheduled task itself here.  On some Windows machines
    # /End also terminates this detached helper before it can issue /Run.
    # Stop only the old Python monitor process, then start the registered task.
    script = (
        f"$owner={os.getpid()}; Start-Sleep -Seconds 2; "
        "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
        "Where-Object { $_.ProcessId -ne $PID -and $_.ProcessId -ne $owner "
        "-and $_.CommandLine -like '*run_printerexp_monitor.py*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }; "
        "Start-Sleep -Seconds 1; "
        "schtasks.exe /Run /TN AutomaticPrintMonitor 2>$null"
    )
    command = [
        "powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script,
    ]
    try:
        subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True,
        )
    except OSError:
        return False
    return True
