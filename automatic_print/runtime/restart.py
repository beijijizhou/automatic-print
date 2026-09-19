from pathlib import Path
import os
import re
import sys

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication

from automatic_print import __version__


# Keep this exactly aligned with dev.py.  The runtime lives two directories
# below the checkout root; using parents[1] leaves an orphan marker inside the
# package that the parent launcher can neither observe nor clear.
PROJECT_ROOT = Path(__file__).parents[2]
RESTART_REQUEST = PROJECT_ROOT / ".restart-request"
SOURCE_VERSION_FILE = Path(__file__).parents[1] / '__init__.py'
UPDATE_GUARD = PROJECT_ROOT / '.update-in-progress'


def source_version_on_disk():
    """Read only the small version marker; never import partially updated code."""
    try:
        content = SOURCE_VERSION_FILE.read_text(encoding='utf-8')
    except OSError:
        return None
    match = re.search(r'^__version__\s*=\s*[\'\"]([^\'\"]+)[\'\"]', content, re.M)
    return match.group(1) if match else None


def source_code_changed():
    version = source_version_on_disk()
    return version is not None and version != __version__


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
        if (PROJECT_ROOT / '.git').exists() and SOURCE_VERSION_FILE.is_file():
            pending, notified = None, False

            def check_source() -> None:
                nonlocal pending, notified
                if UPDATE_GUARD.exists():
                    return
                version = source_version_on_disk()
                if version is None or version == __version__:
                    pending, notified = None, False
                    return
                # Observe the same complete version twice so a checkout in
                # progress cannot restart into a partially written source tree.
                if pending != version:
                    pending = version
                    return
                busy = (window.has_active_tasks()
                        or getattr(window, 'update_thread', None) is not None
                        or window.source_update_busy())
                if busy:
                    if not notified:
                        window.show_update_progress('源码已更新；当前任务完成后自动安全重启…')
                        notified = True
                    return
                timer.stop()
                window.show_update_progress('源码已更新；正在安全重启以加载新版本…')
                if not request_application_restart(window):
                    window.show_update_progress('源码已更新，但自动重启失败；请完成任务后手动重新打开。')

            timer.setInterval(2000)
            timer.timeout.connect(check_source)
            timer.start()
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
