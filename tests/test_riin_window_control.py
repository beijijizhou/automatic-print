"""Win32 probe regression checks independent of the desktop UI dependencies."""
import ctypes
from types import SimpleNamespace
import unittest

from automatic_print.automation.api.riin.window_control import _inspect


class Function:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class RiinWindowControlTests(unittest.TestCase):
    def test_response_uses_pointer_sized_storage_without_activating_window(self):
        calls = []

        def send_message(_hwnd, _message, _wparam, _lparam, _flags, _timeout, result):
            pointer = ctypes.cast(result, ctypes.POINTER(ctypes.c_size_t))
            pointer.contents.value = (1 << (ctypes.sizeof(ctypes.c_void_p) * 8)) - 1
            return 1

        user32 = SimpleNamespace(
            GetWindowTextLengthW=Function(lambda _hwnd: 4),
            GetWindowTextW=Function(lambda _hwnd, buffer, _length: setattr(buffer, 'value', 'RIIN') or 4),
            GetClassNameW=Function(lambda _hwnd, buffer, _length: setattr(buffer, 'value', 'TestWindow') or 10),
            GetWindowThreadProcessId=Function(lambda _hwnd, _pid: 1),
            GetWindowRect=Function(lambda _hwnd, _rect: True),
            SendMessageTimeoutW=Function(send_message),
            ShowWindowAsync=Function(lambda *_args: calls.append('restore')),
            SetForegroundWindow=Function(lambda *_args: calls.append('activate')),
        )
        report = _inspect(user32, 101, activate=False)
        self.assertTrue(report.responsive)
        self.assertFalse(report.activated)
        self.assertEqual(report.title, 'RIIN')
        self.assertEqual(calls, [])
        self.assertEqual(
            ctypes.sizeof(user32.SendMessageTimeoutW.argtypes[-1]._type_),
            ctypes.sizeof(ctypes.c_void_p),
        )
