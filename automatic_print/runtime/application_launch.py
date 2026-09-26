"""Start the fixed AutomaticPrint UI from the resident machine agent."""

import ctypes
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep


APPLICATION_MUTEX = r"Local\AutomaticPrintMainWindow"
ERROR_ALREADY_EXISTS = 183
SYNCHRONIZE = 0x00100000
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_instance_handle = None


def claim_application_instance(*, platform_name=None, kernel32=None):
    """Hold one per-user Windows mutex for the lifetime of the main UI."""
    global _instance_handle
    if (platform_name or os.name) != "nt":
        return True
    api = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
    handle = api.CreateMutexW(None, False, APPLICATION_MUTEX)
    if not handle:
        raise OSError(ctypes.get_last_error(), "无法创建 AutomaticPrint 单实例锁")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        api.CloseHandle(handle)
        return False
    _instance_handle = handle
    return True


def application_running(*, platform_name=None, kernel32=None):
    if (platform_name or os.name) != "nt":
        return False
    api = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
    handle = api.OpenMutexW(SYNCHRONIZE, False, APPLICATION_MUTEX)
    if not handle:
        return False
    api.CloseHandle(handle)
    return True


def application_command(*, executable=None, frozen=None, project_root=PROJECT_ROOT):
    executable = Path(executable or sys.executable)
    is_frozen = bool(getattr(sys, "frozen", False) if frozen is None else frozen)
    if is_frozen:
        application = executable.with_name("AutomaticPrint.exe")
        if not application.is_file():
            raise RuntimeError(f"AutomaticPrint 主程序不存在：{application}")
        return [str(application)], application.parent
    pythonw = executable.with_name("pythonw.exe")
    root = Path(project_root)
    if not pythonw.is_file():
        raise RuntimeError(f"无窗口 Python 不存在：{pythonw}")
    if not (root / "automatic_print" / "__main__.py").is_file():
        raise RuntimeError(f"AutomaticPrint 源码入口不存在：{root}")
    return [str(pythonw), "-m", "automatic_print"], root


def launch_application(
    *, running=None, spawn=None, wait=sleep, clock=monotonic, timeout=12,
):
    """Start only AutomaticPrint and wait for its single-instance receipt."""
    is_running = running or application_running
    if is_running():
        return {"launched": False, "already_running": True}
    command, working_directory = application_command()
    (spawn or _spawn_application)(command, working_directory)
    deadline = clock() + float(timeout)
    while clock() < deadline:
        if is_running():
            return {"launched": True, "already_running": False}
        wait(0.2)
    raise RuntimeError("已启动 AutomaticPrint，但未在限时内检测到主界面。")


def _spawn_application(command, working_directory):
    flags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    )
    subprocess.Popen(
        command,
        cwd=str(working_directory),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )
