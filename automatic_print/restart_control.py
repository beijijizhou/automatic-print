from pathlib import Path

from PySide6.QtCore import QTimer


RESTART_REQUEST = Path(__file__).parents[1] / ".restart-request"


def install_restart_monitor(application, window) -> QTimer:
    timer = QTimer(application)
    timer.setInterval(250)

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
