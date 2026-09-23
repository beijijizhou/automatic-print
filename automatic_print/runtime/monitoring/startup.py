"""Self-heal the persistent PrintExp monitor for source and packaged installs."""

import logging
import os
from pathlib import Path
import subprocess
import sys


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "AutomaticPrintMonitor"
SCHEDULED_TASK = "AutomaticPrintMonitor"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def ensure_monitor_started(
    *, project_root=PROJECT_ROOT, executable=None, frozen=None,
    platform_name=None, register=None, spawn=None, start_scheduled=None,
    unregister=None, stop_existing=None,
):
    """Start the elevated monitor task, with a status-only fallback."""
    if (platform_name or os.name) != "nt":
        return False
    try:
        (stop_existing or _stop_existing_monitors)()
        if (start_scheduled or _start_scheduled_monitor)():
            (unregister or _remove_run_value)()
            return True
        command, working_directory = monitor_command(
            project_root=project_root, executable=executable, frozen=frozen,
        )
        command_text = subprocess.list2cmdline(command)
        (register or _register_run_value)(command_text)
        (spawn or _spawn_monitor)(command, working_directory)
        return True
    except (OSError, ValueError) as error:
        logging.getLogger("automatic-print.startup").warning(
            "Unable to register PrintExp monitor: %s", error,
        )
        return False


def monitor_command(*, project_root=PROJECT_ROOT, executable=None, frozen=None):
    executable = Path(executable or sys.executable)
    is_frozen = bool(getattr(sys, "frozen", False) if frozen is None else frozen)
    if is_frozen:
        monitor = executable.with_name("AutomaticPrintMonitor.exe")
        if not monitor.is_file():
            raise ValueError(f"后台监控程序不存在：{monitor}")
        return [str(monitor)], monitor.parent
    root = Path(project_root)
    script = root / "run_printerexp_monitor.py"
    pythonw = executable.with_name("pythonw.exe")
    if not script.is_file():
        raise ValueError(f"后台监控入口不存在：{script}")
    if not pythonw.is_file():
        raise ValueError(f"无窗口 Python 不存在：{pythonw}")
    return [str(pythonw), str(script)], root


def _register_run_value(command):
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)


def _remove_run_value():
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, RUN_VALUE)
    except FileNotFoundError:
        pass


def _start_scheduled_monitor():
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["schtasks.exe", "/End", "/TN", SCHEDULED_TASK],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        creationflags=flags,
    )
    result = subprocess.run(
        ["schtasks.exe", "/Run", "/TN", SCHEDULED_TASK],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        creationflags=flags,
    )
    return result.returncode == 0


def _stop_existing_monitors():
    """Release the old source monitor lock after an in-app code update."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    script = (
        f"$owner={os.getpid()}; "
        "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
        "Where-Object { $_.ProcessId -ne $PID -and $_.ProcessId -ne $owner "
        "-and $_.CommandLine -like '*run_printerexp_monitor.py*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _spawn_monitor(command, working_directory):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(
        command,
        cwd=str(working_directory),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )
