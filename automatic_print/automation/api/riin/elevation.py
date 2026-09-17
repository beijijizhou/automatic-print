"""Launch one explicit RIIN operation using the Windows consent prompt."""
import ctypes
from pathlib import Path
import subprocess
import sys


def is_administrator():
    return sys.platform == 'win32' and bool(ctypes.windll.shell32.IsUserAnAdmin())


def launch_elevated(arguments):
    if sys.platform != 'win32':
        raise OSError('RIIN控制入口只能在Windows运行。')
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.ShellExecuteW.argtypes = (
        ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
        ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int,
    )
    shell.ShellExecuteW.restype = ctypes.c_void_p
    root = Path(__file__).resolve().parents[4]
    command = subprocess.list2cmdline([
        '-m', 'automatic_print.automation.api.riin', *arguments,
    ])
    result = shell.ShellExecuteW(None, 'runas', sys.executable, command, str(root), 0)
    if not result or result <= 32:
        raise OSError('管理员控制入口未启动；可确认Windows授权后重新运行。')

