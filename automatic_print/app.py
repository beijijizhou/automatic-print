from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from .resources import asset_path

__all__ = ["run"]


def run() -> int:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    application.setApplicationName("Haloo Automatic")
    application.setWindowIcon(QIcon(str(asset_path("ha-icon.ico"))))
    background = QPixmap(540, 160)
    background.fill(Qt.white)
    splash = QSplashScreen(background)
    splash.showMessage('正在启动本地排版工作台…\n正在加载界面组件，图片分析将在主界面显示后开始。',
                       Qt.AlignCenter, Qt.black)
    splash.show()
    application.processEvents()
    from .ui.main_window import MainWindow
    from .restart_control import install_restart_monitor

    window = MainWindow()
    application.automatic_print_window = window
    install_restart_monitor(application, window)
    window.show()
    splash.finish(window)
    return application.exec()
