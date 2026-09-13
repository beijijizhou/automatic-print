import os
import sys
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from ..updates.source import PROJECT_ROOT


def restart_updated_app(window):
    window.automation_home.setEnabled(True)
    window.settings_dialog.setEnabled(True)
    if window.source_update_busy():
        window.show_update_progress('更新完成；仍有任务运行，请完成后手动重新启动。')
        return
    if os.environ.get('AUTOMATIC_PRINT_DEV') == '1':
        (PROJECT_ROOT/'.restart-request').touch()
        window.show_update_progress('更新完成，正在请求安全重启…')
        return
    started, _pid = QProcess.startDetached(sys.executable, ['-m', 'automatic_print'], str(PROJECT_ROOT))
    if not started:
        window.show_update_progress('更新完成，但自动启动失败；请使用桌面入口重新打开。')
        return
    window.close()
    QApplication.instance().quit()
