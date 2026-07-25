from PySide6.QtCore import QTimer


def thread_is_running(thread) -> bool:
    if thread is None:
        return False
    try:
        return thread.isRunning()
    except RuntimeError:
        return False


def discard_stopped_thread(owner, thread_name: str, worker_name: str) -> bool:
    thread = getattr(owner, thread_name, None)
    if thread_is_running(thread):
        return False
    setattr(owner, thread_name, None)
    setattr(owner, worker_name, None)
    return True


def defer_finished_thread_cleanup(
    owner, thread_name: str, worker_name: str
) -> None:
    """Keep wrappers alive until Qt has finished dispatching `finished`."""
    thread = getattr(owner, thread_name, None)
    worker = getattr(owner, worker_name, None)
    if thread is None:
        setattr(owner, worker_name, None)
        return

    def release_references() -> None:
        if getattr(owner, thread_name, None) is thread:
            setattr(owner, thread_name, None)
        if getattr(owner, worker_name, None) is worker:
            setattr(owner, worker_name, None)

    def request_qt_deletion() -> None:
        try:
            thread.deleteLater()
        except RuntimeError:
            pass
        QTimer.singleShot(0, release_references)

    QTimer.singleShot(0, request_qt_deletion)
