"""Compact busy indicator for work whose total size is not yet known."""
from math import cos, pi, sin

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class BusySpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame = 0
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._advance)
        self.setFixedSize(26, 26)
        self.setToolTip('正在处理')
        self.hide()

    def start(self) -> None:
        self.show()
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def isActive(self) -> bool:
        return self._timer.isActive()

    def _advance(self) -> None:
        self._frame = (self._frame + 1) % 12
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            center = self.rect().center()
            for index in range(12):
                color = QColor('#2563eb')
                color.setAlpha(45 + ((index - self._frame) % 12) * 18)
                painter.setBrush(color)
                angle = index * pi / 6
                x = center.x() + 8 * cos(angle) - 2
                y = center.y() + 8 * sin(angle) - 2
                painter.drawEllipse(int(x), int(y), 4, 4)
        finally:
            painter.end()


def show_busy(window) -> None:
    window.progress.hide()
    if getattr(window, 'compact_status_only', False):
        window.busy_spinner.stop()
        return
    window.busy_spinner.start()


def show_progress(window) -> None:
    window.busy_spinner.stop()
    if getattr(window, 'compact_status_only', False):
        window.progress.hide()
        return
    window.progress.show()
