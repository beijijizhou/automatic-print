from time import monotonic
from PySide6.QtTest import QTest


def wait_preview(preview, timeout=10):
    deadline = monotonic()+timeout
    while preview.refresh_timer.isActive() or preview.loader.active or preview.loader.pending:
        assert monotonic() < deadline, '后台预览未按时结束'
        QTest.qWait(10)
