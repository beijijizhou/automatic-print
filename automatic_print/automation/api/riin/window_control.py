"""Discover and safely probe RIIN windows in the interactive Windows session."""
from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import sys


WM_NULL = 0x0000
SMTO_ABORTIFHUNG = 0x0002
SW_RESTORE = 9


@dataclass(frozen=True)
class RiinWindow:
    handle: int
    process_id: int
    title: str
    class_name: str
    bounds: tuple[int, int, int, int]
    responsive: bool
    activated: bool


@dataclass(frozen=True)
class RiinProbeReport:
    keyword: str
    windows: tuple[RiinWindow, ...] = ()
    error: str = ''

    @property
    def found(self):
        return bool(self.windows)


def probe_riin(keyword='RIIN', activate=True):
    """Find matching top-level windows and perform only a WM_NULL/focus probe."""
    keyword = keyword.strip() or 'RIIN'
    if sys.platform != 'win32':
        return RiinProbeReport(keyword, error='RIIN控制测试只能在Windows桌面会话运行。')
    try:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        matches = _matching_windows(user32, keyword)
        windows = tuple(_inspect(user32, hwnd, activate) for hwnd in matches)
        return RiinProbeReport(keyword, windows)
    except Exception as exc:
        return RiinProbeReport(keyword, error=f'Windows窗口探测失败：{exc}')


def _matching_windows(user32, keyword):
    matches = []
    callback_factory = getattr(ctypes, 'WINFUNCTYPE', ctypes.CFUNCTYPE)
    callback_type = callback_factory(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def collect(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        if keyword.casefold() in buffer.value.casefold():
            matches.append(int(hwnd))
        return True

    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    if not user32.EnumWindows(collect, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return matches


def _inspect(user32, hwnd, activate):
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, wintypes.LPDWORD)
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.SendMessageTimeoutW.argtypes = (
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
    )
    user32.SendMessageTimeoutW.restype = wintypes.LPARAM
    user32.ShowWindowAsync.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.ShowWindowAsync.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL
    title = _text(user32.GetWindowTextLengthW, user32.GetWindowTextW, hwnd)
    class_buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_buffer, len(class_buffer))
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    response = ctypes.c_size_t()
    responsive = bool(user32.SendMessageTimeoutW(
        hwnd, WM_NULL, 0, 0, SMTO_ABORTIFHUNG, 1000, ctypes.byref(response)))
    activated = False
    if activate:
        user32.ShowWindowAsync(hwnd, SW_RESTORE)
        activated = bool(user32.SetForegroundWindow(hwnd))
    return RiinWindow(
        hwnd, int(process_id.value), title, class_buffer.value,
        (rect.left, rect.top, rect.right, rect.bottom), responsive, activated,
    )


def _text(length_function, text_function, hwnd):
    buffer = ctypes.create_unicode_buffer(max(1, length_function(hwnd) + 1))
    text_function(hwnd, buffer, len(buffer))
    return buffer.value
