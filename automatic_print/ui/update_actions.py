from PySide6.QtCore import QThread, Qt, QUrl, Slot, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from .. import __version__, __version_display__
from ..updates.release import version_tuple
from ..updates.source import source_install, SourceUpdateInfo
from ..updates.worker import SourceUpdateWorker
from ..runtime.restart import source_code_changed
from .workers import UpdateWorker
from .thread_lifecycle import defer_finished_thread_cleanup, discard_stopped_thread
from .update_restart import restart_updated_app


class UpdateActionsMixin:
    def build_update_status(self):
        self.source_update_applying = False
        self.pending_source_update = None
        self.completed_source_check = None
        self.update_restart_pending = False

    @Slot(str)
    def show_update_progress(self, _text):
        """Keep update worker compatibility without exposing update steps in the UI."""

    def check_for_updates(self, silent: bool) -> None:
        if self.update_thread is not None and not discard_stopped_thread(self, 'update_thread', 'update_worker'):
            return
        self.update_is_silent = silent
        worker = SourceUpdateWorker() if source_install() else UpdateWorker()
        self.start_update_worker(worker)

    def start_update_worker(self, worker):
        self.update_thread = QThread(self)
        self.update_worker = worker
        worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(worker.run)
        bridge, queued = self.worker_bridge, Qt.QueuedConnection
        worker.finished.connect(bridge.update_finished, queued)
        worker.failed.connect(bridge.update_failed, queued)
        if isinstance(worker, SourceUpdateWorker):
            worker.progress.connect(bridge.update_progress, queued)
        worker.finished.connect(self.update_thread.quit, Qt.DirectConnection)
        worker.failed.connect(self.update_thread.quit, Qt.DirectConnection)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        self.update_thread.finished.connect(self.clear_update_worker)
        self.update_thread.start()

    def source_update_busy(self):
        p = self.automation_home.label_quick_panel.preview
        return (self.thread is not None or self.automation_home.thread is not None
                or p.production_active or p.loader.active is not None
                or p.loader.pending is not None or p.refresh_timer.isActive())

    @Slot(object)
    def update_check_finished(self, update):
        if isinstance(update, SourceUpdateInfo):
            if self.source_update_applying:
                self.show_update_progress('代码和依赖已更新，正在安全重启…')
                self.update_restart_pending = True
                return
            self.completed_source_check = update
            if not update.needs_update:
                self.show_update_progress(
                    '源码已更新；当前任务完成后自动安全重启…' if source_code_changed()
                    else f'源码已是最新 · {update.display_version}')
            elif not self.update_is_silent and self.source_update_busy():
                self.show_update_progress('发现新代码；当前生产任务结束后，下次启动会重新检查。')
            else:
                self.show_update_progress(f'发现源码更新：{update.display_version} · {update.commits} 个新提交')
            return
        if version_tuple(update.version) > version_tuple(__version__):
            answer = QMessageBox.question(self, '发现新版本',
                f'{update.display_version}\n当前为安装包安装，请下载新版安装程序。\n是否打开下载页面？',
                QMessageBox.Yes | QMessageBox.No)
            if answer == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(update.download_url))
        else:
            self.show_update_progress(f'已经是最新版 · {__version_display__}')

    def confirm_source_check(self, update):
        if not update.needs_update:
            self.show_update_progress(
                '源码已更新；当前任务完成后自动安全重启…' if source_code_changed()
                else f'源码已是最新 · {update.display_version}')
            return
        self.show_update_progress(f'发现源码更新：{update.display_version} · {update.commits} 个新提交')
        if self.update_is_silent:
            return
        if self.source_update_busy():
            self.show_update_progress('发现新代码；当前生产任务结束后，下次启动会重新检查。')
            return
        answer = QMessageBox.question(self, '发现源码更新',
            f'新版本：{update.display_version}\n当前版本：{__version_display__}\n\n'
            '直接更新代码和运行依赖，完成后安全重启；无需安装包。\n是否立即更新？',
            QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.pending_source_update = update

    def apply_source_update(self):
        info = self.pending_source_update
        self.pending_source_update = None
        if not info:
            return
        if self.source_update_busy():
            self.show_update_progress('有任务正在执行，更新已暂停；下次启动会重新检查。')
            return
        self.preference_autosave.flush()
        self.source_update_applying = True
        self.automation_home.setEnabled(False)
        self.settings_dialog.setEnabled(False)
        self.start_update_worker(SourceUpdateWorker(info))

    @Slot(str)
    def update_check_failed(self, message):
        self.pending_source_update = None
        self.completed_source_check = None
        self.show_update_progress(f'更新未完成：{message}\n下次启动会自动重试；不会覆盖本地修改。')
        if not self.update_is_silent or self.source_update_applying:
            QMessageBox.warning(self, '更新未完成', message)

    @Slot()
    def clear_update_worker(self):
        defer_finished_thread_cleanup(self, 'update_thread', 'update_worker')
        QTimer.singleShot(30, self.update_cleanup_finished)

    def update_cleanup_finished(self):
        if self.update_thread is not None:
            QTimer.singleShot(30, self.update_cleanup_finished)
            return
        if self.update_restart_pending:
            self.update_restart_pending = False
            self.source_update_applying = False
            restart_updated_app(self)
            return
        self.source_update_applying = False
        self.automation_home.setEnabled(True)
        self.settings_dialog.setEnabled(True)
        update = self.completed_source_check
        self.completed_source_check = None
        if update is not None:
            self.confirm_source_check(update)
        self.apply_source_update()
