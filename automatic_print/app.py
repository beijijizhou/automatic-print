from PySide6.QtWidgets import QApplication

__all__ = ["run"]


def run() -> int:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    from .ui.main_window import MainWindow

    window = MainWindow()
    application.automatic_print_window = window
    window.show()
    return application.exec()
