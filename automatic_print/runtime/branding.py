"""Shared application identity for source and packaged desktop launches."""
import ctypes
import logging
import sys

from PySide6.QtGui import QIcon

from .resources import asset_path

WINDOWS_APP_ID = "Haloo.AutomaticPrint.Desktop"


def configure_windows_identity():
    """Must run before QApplication creates any native Windows UI."""
    if sys.platform != "win32":
        return False
    try:
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        set_id = shell.SetCurrentProcessExplicitAppUserModelID
        set_id.argtypes = [ctypes.c_wchar_p]
        set_id.restype = ctypes.c_long
        result = set_id(WINDOWS_APP_ID)
        if result < 0:
            raise OSError(f"AppUserModelID HRESULT: {result}")
        return True
    except (AttributeError, OSError) as error:
        logging.getLogger(__name__).warning("Windows 应用标识设置失败：%s", error)
        return False


def application_icon():
    icon = QIcon(str(asset_path("ha-icon.ico")))
    if icon.isNull():
        icon = QIcon(str(asset_path("ha-icon.png")))
    return icon


def configure_application(application):
    application.setApplicationName("Haloo Automatic")
    application.setWindowIcon(application_icon())
