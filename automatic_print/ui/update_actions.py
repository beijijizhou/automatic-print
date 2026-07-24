from PySide6.QtCore import QThread, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from .. import __version__
from ..updater import UpdateInfo, version_tuple
from .workers import UpdateWorker


class UpdateActionsMixin:
    def check_for_updates(self, silent: bool) -> None:
        if self.update_thread is not None:
            return
        self.update_is_silent = silent
        self.check_update_button.setEnabled(False)
        self.check_update_button.setText("正在检查…")
        self.update_thread = QThread(self)
        self.update_worker = UpdateWorker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        queued = Qt.ConnectionType.QueuedConnection
        self.update_worker.finished.connect(
            self.update_check_finished, queued
        )
        self.update_worker.failed.connect(
            self.update_check_failed, queued
        )
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.failed.connect(self.update_thread.quit)
        self.update_thread.finished.connect(
            self.update_worker.deleteLater
        )
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.finished.connect(self.clear_update_worker)
        self.update_thread.start()

    @Slot(object)
    def update_check_finished(self, update: UpdateInfo) -> None:
        if version_tuple(update.version) > version_tuple(__version__):
            answer = QMessageBox.question(
                self,
                "发现新版本",
                f"自动打印排版 {update.version} 已发布。\n\n"
                f"当前版本：{__version__}\n\n"
                "是否打开安装程序下载页面？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(update.download_url))
        elif not self.update_is_silent:
            QMessageBox.information(
                self,
                "已经是最新版",
                f"自动打印排版 {__version__} 已经是最新版本。",
            )

    @Slot(str)
    def update_check_failed(self, message: str) -> None:
        if not self.update_is_silent:
            QMessageBox.warning(
                self, "检查更新失败", f"暂时无法检查更新。\n\n{message}"
            )

    @Slot()
    def clear_update_worker(self) -> None:
        self.update_thread = None
        self.update_worker = None
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText("检查更新")
