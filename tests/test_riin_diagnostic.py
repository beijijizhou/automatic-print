import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from automatic_print.automation.api.riin import RiinProbeReport, RiinWindow
from automatic_print.automation.api.riin.window_control import probe_riin
from automatic_print.ui.riin_diagnostic import RiinDiagnosticDialog


APP = QApplication.instance() or QApplication([])


def test_probe_reports_unsupported_platform(monkeypatch):
    monkeypatch.setattr('automatic_print.automation.api.riin.window_control.sys.platform', 'darwin')
    report = probe_riin('RIIN')
    assert not report.found
    assert 'Windows' in report.error


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
