import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image

from automatic_print.resources import asset_path
from automatic_print import branding

UI_OWNERS = []


def test_ha_icon_contains_windows_sizes() -> None:
    icon = asset_path("ha-icon.ico")
    assert icon.is_file()
    with Image.open(icon) as image:
        assert {(16, 16), (32, 32), (256, 256)} <= image.ico.sizes()


def test_test_computer_setup_creates_desktop_shortcut() -> None:
    root = Path(__file__).parents[1]
    script = (
        root / "windows" / "bootstrap-test-computer.ps1"
    ).read_text(encoding="utf-8")

    assert '"Haloo Automatic.lnk"' in script
    assert '"assets\\ha-icon.ico"' in script
    assert "$shortcut.Save()" in script


def test_windows_identity_is_explicit_and_stable(monkeypatch):
    calls = []
    class Setter:
        def __call__(self, value):
            calls.append(value)
            return 0
    class Shell:
        SetCurrentProcessExplicitAppUserModelID = Setter()
    monkeypatch.setattr(branding.sys, 'platform', 'win32')
    monkeypatch.setattr(branding.ctypes, 'WinDLL', lambda *a, **k: Shell(), raising=False)
    assert branding.configure_windows_identity()
    assert calls == ['Haloo.AutomaticPrint.Desktop']
    assert Shell.SetCurrentProcessExplicitAppUserModelID.argtypes == [branding.ctypes.c_wchar_p]


def test_identity_failure_does_not_prevent_startup(monkeypatch):
    monkeypatch.setattr(branding.sys, 'platform', 'win32')
    def unavailable(*args, **kwargs):
        raise OSError('unavailable')
    monkeypatch.setattr(branding.ctypes, 'WinDLL', unavailable, raising=False)
    assert not branding.configure_windows_identity()


def test_non_windows_does_not_load_shell(monkeypatch):
    monkeypatch.setattr(branding.sys, 'platform', 'darwin')
    def forbidden(*args, **kwargs):
        raise AssertionError('must not load Windows DLL')
    monkeypatch.setattr(branding.ctypes, 'WinDLL', forbidden, raising=False)
    assert not branding.configure_windows_identity()


def test_runtime_window_and_dialog_use_ha_icon(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from automatic_print.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    UI_OWNERS.append(app)
    branding.configure_application(app)
    window = MainWindow(QSettings(str(tmp_path/'icon.ini'), QSettings.IniFormat))
    UI_OWNERS.append(window)
    window.startup_update_timer.stop()
    assert not app.windowIcon().isNull()
    assert not window.windowIcon().isNull()
    assert not window.settings_dialog.windowIcon().isNull()
    assert window.windowIcon().cacheKey() == window.settings_dialog.windowIcon().cacheKey()
    assert not window.windowIcon().pixmap(32, 32).isNull()
    window.close()
