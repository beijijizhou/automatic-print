import re
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from .worker import AutomationWorker
from ..ui.thread_lifecycle import (
    defer_finished_thread_cleanup,
    discard_stopped_thread,
)


class ThreadActionsMixin:
    def _start_worker(self, worker: AutomationWorker) -> None:
        if self.thread is not None:
            if not discard_stopped_thread(self, "thread", "worker"):
                return
        self._set_actions_enabled(False)
        self.loading_bar.setRange(0, 0)
        self.loading_label.setText(
            f"正在处理 {worker.platform_name}，请稍候…"
        )
        self.loading_panel.show()
        self.thread = QThread(self)
        self.worker = worker
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        queued = Qt.ConnectionType.QueuedConnection
        bridge = self.worker_bridge
        worker.progress.connect(bridge.progress, queued)
        worker.batches_loaded.connect(bridge.batches_loaded, queued)
        worker.status_loaded.connect(bridge.status_loaded, queued)
        worker.plan_loaded.connect(bridge.plan_loaded, queued)
        worker.completed.connect(bridge.completed, queued)
        worker.failed.connect(bridge.failed, queued)
        terminal = {
            "list": worker.batches_loaded,
            "list_range": worker.batches_loaded,
            "status": worker.status_loaded,
            "status_and_list": worker.batches_loaded,
            "preview_rules": worker.plan_loaded,
            "generate_rules": worker.completed,
            "download": worker.completed,
            "process": worker.completed,
        }[worker.action]
        terminal.connect(worker.deleteLater)
        terminal.connect(self.thread.quit)
        worker.failed.connect(worker.deleteLater)
        worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

    @Slot(str)
    def append_log(self, message: str) -> None:
        self.log.appendPlainText(message)

    @Slot(str)
    def show_progress_message(self, message: str) -> None:
        self.loading_label.setText(message)
        step = re.search(r"\[(\d+)/(\d+)\]", message)
        if step:
            current, total = map(int, step.groups())
            self.loading_bar.setRange(0, total)
            self.loading_bar.setValue(current)
            self.loading_bar.setTextVisible(True)
            self.loading_bar.setFormat(f"{current} / {total}")
        else:
            self.loading_bar.setRange(0, 0)
            self.loading_bar.setTextVisible(False)

    @Slot(object)
    def action_finished(self, result: dict) -> None:
        if result["type"] == "batches_generated":
            self.pending_batch_plan = None
            self.generate_rules_button.setEnabled(False)
            text = (
                f"{result['platform']}：已成功生成 "
                f"{result['generated']} 个分类批次。"
            )
            self.batch_rule_summary.setText(text)
            QMessageBox.information(self, "批次生成完成", text)
            return
        mode = "测试小样" if result["test"] else "生产批次"
        if result["type"] == "downloaded_and_processed":
            text = (
                f"{result['platform']}：已下载并解压 "
                f"{len(result['files'])} 个文件，已完成 "
                f"{len(result['batches'])} 个{mode}排版。"
            )
            self.refresh_local_batches()
        else:
            text = (
                f"{result['platform']}：已生成 "
                f"{len(result['batches'])} 个{mode}排版图片。"
            )
        self.summary.setText(text)
        QMessageBox.information(self, "处理完成", text)
        folder = Path(result["output_folder"])
        if folder.is_dir():
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(folder.resolve()))
            )

    @Slot(str)
    def failed(self, message: str) -> None:
        self.log.appendPlainText(f"停止：{message}")
        QMessageBox.critical(self, "操作已停止", message)

    def _set_actions_enabled(self, enabled: bool) -> None:
        for widget in (
            self.platform,
            self.main_tabs,
            self.refresh_button,
            self.select_button,
            self.download_button,
            self.process_button,
            self.range_button,
            self.settings_button,
            self.preview_rules_button,
            self.local_refresh_button,
            self.local_select_button,
            self.local_process_button,
            self.local_open_button,
        ):
            widget.setEnabled(enabled)
        plan = self.pending_batch_plan
        self.generate_rules_button.setEnabled(
            enabled
            and plan is not None
            and bool(plan.nonempty_items)
            and plan.total_items + plan.excluded_count == plan.received_count
        )

    @Slot()
    def clear_worker(self) -> None:
        self.loading_panel.hide()
        self._set_actions_enabled(True)
        defer_finished_thread_cleanup(self, "thread", "worker")
