from pathlib import Path
import os
import sys

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication


RESTART_REQUEST = Path(__file__).parents[1] / ".restart-request"


def request_application_restart(window) -> bool:
    """Restart the current installation without duplicating launch policy."""
    if os.environ.get('AUTOMATIC_PRINT_DEV') == '1':
        RESTART_REQUEST.touch()
        return True
    started, _pid = QProcess.startDetached(
        sys.executable, ['-m', 'automatic_print'], str(RESTART_REQUEST.parent))
    if started:
        window.close()
        QApplication.instance().quit()
    return started


def install_restart_monitor(application, window) -> QTimer:
    timer = QTimer(application)
    timer.setInterval(250)

    if os.environ.get('AUTOMATIC_PRINT_DEV') != '1':
        # A source checkout is often launched directly from a desktop shortcut.
        # Only dev.py has a parent process capable of honoring this marker and
        # starting the child again.  A stale marker must never close a normal
        # launch and leave the user with what looks like a startup crash.
        RESTART_REQUEST.unlink(missing_ok=True)
        application.automatic_print_restart_timer = timer
        return timer

    def check() -> None:
        if not RESTART_REQUEST.exists():
            return
        if window.has_active_tasks():
            return
        timer.stop()
        window.close()
        application.quit()

    timer.timeout.connect(check)
    timer.start()
    application.automatic_print_restart_timer = timer
    return timer
