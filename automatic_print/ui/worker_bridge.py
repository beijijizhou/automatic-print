from PySide6.QtCore import QObject, Signal


class MainWindowWorkerBridge(QObject):
    """Routes worker results through an object owned by the GUI thread."""

    layout_progress = Signal(str, int, object, str)
    layout_finished = Signal(str, object)
    layout_failed = Signal(str)
    layout_cancelled = Signal()
    update_finished = Signal(object)
    update_failed = Signal(str)


class BatchWorkerBridge(QObject):
    """Routes ERP worker results through an object owned by the GUI thread."""

    progress = Signal(str)
    batches_loaded = Signal(object)
    status_loaded = Signal(object)
    plan_loaded = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
