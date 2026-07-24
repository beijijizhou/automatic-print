from PySide6.QtWidgets import QApplication

__all__ = ["run"]


def run() -> int:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    from .ui.main_window import MainWindow
    from .restart_control import install_restart_monitor

    window = MainWindow()
    application.automatic_print_window = window
    install_restart_monitor(application, window)
    window.show()
    return application.exec()
