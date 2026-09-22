import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from automatic_print.automation.api.riin import RiinProbeReport, RiinWindow
from automatic_print.automation.api.riin.desktop_controls.window_control import _matching_windows, probe_riin
from automatic_print.ui.riin_diagnostic import RiinDiagnosticDialog


APP = QApplication.instance() or QApplication([])


def test_probe_reports_unsupported_platform(monkeypatch):
    monkeypatch.setattr('automatic_print.automation.api.riin.desktop_controls.window_control.sys.platform', 'darwin')
    report = probe_riin('RIIN')
    assert not report.found
    assert 'Windows' in report.error


class FakeFunction:
    def __init__(self, function):
        self.function = function
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.function(*args)


def test_enum_windows_declares_generated_callback_type():
    callbacks = []

    class User32:
        IsWindowVisible = FakeFunction(lambda _hwnd: True)
        GetWindowTextLengthW = FakeFunction(lambda _hwnd: len('RIIN Main'))
        GetWindowTextW = FakeFunction(
            lambda _hwnd, buffer, _length: setattr(buffer, 'value', 'RIIN Main') or 9)

        def __init__(self):
            self.EnumWindows = FakeFunction(self.enumerate)

        def enumerate(self, callback, _lparam):
            callbacks.append(callback)
            return callback(101, 0)

    user32 = User32()
    assert _matching_windows(user32, 'RIIN') == [101]
    assert user32.EnumWindows.argtypes[0] is type(callbacks[0])


def test_dialog_explains_safe_success_and_foreground_limit():
    dialog = RiinDiagnosticDialog()
    report = RiinProbeReport('RIIN', (
        RiinWindow(101, 202, 'RIIN Main', 'MainWindow', (1, 2, 801, 602), True, True),
        RiinWindow(102, 203, 'RIIN Queue', 'Dialog', (3, 4, 403, 304), True, False),
    ))
    dialog.show_report(report)
    text = dialog.result.toPlainText()
    assert '发现 2 个匹配窗口' in text
    assert '已接受置前请求' in text
    assert '系统未允许置前' in text
    assert '按钮级自动化' in text
    dialog.close()


def test_dialog_keeps_missing_window_recoverable():
    dialog = RiinDiagnosticDialog()
    dialog.show_report(RiinProbeReport('Maintop'))
    text = dialog.result.toPlainText()
    assert '未发现' in text
    assert '修改上方关键字后重试' in text
    dialog.close()
