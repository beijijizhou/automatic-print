from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow

__all__ = ["MainWindow", "run"]


def run() -> int:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return application.exec()
