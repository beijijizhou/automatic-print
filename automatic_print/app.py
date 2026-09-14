from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from .branding import configure_windows_identity, configure_application, application_icon

__all__ = ["run"]


def run() -> int:
    configure_windows_identity()
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    configure_application(application)
    from .ui.copyable_text import install_text_copying
    install_text_copying()
    background = QPixmap(540, 160)
    background.fill(Qt.white)
    splash = QSplashScreen(background)
    splash.setWindowIcon(application_icon())
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
