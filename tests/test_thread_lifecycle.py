from PySide6.QtCore import QCoreApplication

from automatic_print.ui.thread_lifecycle import discard_stopped_thread
from automatic_print.ui.worker_bridge import (
    BatchWorkerBridge,
    MainWindowWorkerBridge,
)


class Owner:
    pass


class Thread:
    def __init__(self, running: bool) -> None:
        self.running = running

    def isRunning(self) -> bool:
        return self.running


def test_stopped_thread_reference_is_discarded() -> None:
    owner = Owner()
    owner.thread = Thread(False)
    owner.worker = object()

    assert discard_stopped_thread(owner, "thread", "worker")
    assert owner.thread is None
    assert owner.worker is None


def test_running_thread_is_preserved() -> None:
    owner = Owner()
    owner.thread = Thread(True)
    owner.worker = object()

    assert not discard_stopped_thread(owner, "thread", "worker")
    assert owner.thread is not None
    assert owner.worker is not None


def test_worker_bridges_stay_in_gui_thread() -> None:
    application = QCoreApplication.instance() or QCoreApplication([])

    assert MainWindowWorkerBridge().thread() is application.thread()
    assert BatchWorkerBridge().thread() is application.thread()
