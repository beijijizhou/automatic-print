"""Locate a portable PrintExp installation and detect its process."""

import ctypes
import os
from pathlib import Path


EXECUTABLE_NAMES = {"printexp.exe", "printexp_x64.exe"}


def find_installation():
    configured = os.environ.get("AUTOMATIC_PRINT_PRINTEXP_DIR", "").strip()
    if configured:
        result = _installation(Path(configured))
        if result:
            return result
    cached = _cache_file()
    try:
        result = _installation(Path(cached.read_text(encoding="utf-8").strip()))
        if result:
            return result
    except (OSError, UnicodeError):
        pass
    for root in _search_roots():
        if not root.is_dir():
            continue
        try:
            executables = root.rglob("PrintExp*.exe")
            for executable in executables:
                if executable.name.casefold() not in EXECUTABLE_NAMES:
                    continue
                result = _installation(executable.parent)
                if result:
                    _remember(result)
                    return result
        except OSError:
            continue
    return None


def process_running():
    return bool(_printerexp_processes())


def running_installations():
    """Return installations that own a currently running PrintExp process."""
    installations = []
    for process_id, _name in _printerexp_processes():
        executable = _process_image(process_id)
        result = _installation(executable.parent) if executable else None
        if result and result not in installations:
            installations.append(result)
    return installations


def _printerexp_processes():
    if os.name != "nt":
        return []
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return []
    entry = _ProcessEntry()
    entry.dwSize = ctypes.sizeof(entry)
    results = []
    try:
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.szExeFile.casefold() in EXECUTABLE_NAMES:
                results.append((entry.th32ProcessID, entry.szExeFile))
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return results


def _process_image(process_id):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel.OpenProcess(0x1000, False, process_id)
    if not handle:
        return None
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return Path(buffer.value)
    finally:
        kernel.CloseHandle(handle)
    return None


def _installation(path):
    if path.is_file():
        path = path.parent
    if (path / "Data" / "PrintInfo.ini").is_file():
        return path
    return None


def _search_roots():
    home = Path.home()
    roots = [home / "Desktop"]
    onedrive = os.environ.get("OneDrive", "").strip()
    if onedrive:
        roots.append(Path(onedrive) / "Desktop")
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(variable, "").strip()
        if value:
            roots.append(Path(value))
    return roots


def _cache_file():
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".automatic-print")
    return root / "AutomaticPrint" / "printerexp-location.txt"


def _remember(path):
    target = _cache_file()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(path), encoding="utf-8")
    except OSError:
        pass


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong), ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_wchar * 260),
    ]
