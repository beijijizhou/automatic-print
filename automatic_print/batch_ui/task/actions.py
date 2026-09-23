import re
from PySide6.QtCore import QThread, Qt, Slot, QTimer
from PySide6.QtWidgets import QMessageBox

from .worker import AutomationWorker
from ...ui.thread_lifecycle import (
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
        self.stop_button.setEnabled(True)
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
        worker.cancelled.connect(bridge.cancelled, queued)
        terminal = {
            "read": worker.completed,
            "list": worker.batches_loaded,
            "list_range": worker.batches_loaded,
            "status": worker.status_loaded,
            "status_and_list": worker.batches_loaded,
            "preview_rules": worker.plan_loaded,
            "preview_route": worker.plan_loaded,
            "generate_route": worker.completed,
            "preview_default_multi": worker.plan_loaded,
            "generate_default_multi": worker.completed,
            "generate_rules": worker.completed,
            "generate_completed_erp": worker.completed,
            "download": worker.completed,
            "process": worker.completed,
        }[worker.action]
        terminal.connect(worker.deleteLater)
        terminal.connect(self.thread.quit)
        worker.failed.connect(worker.deleteLater)
        worker.failed.connect(self.thread.quit)
        worker.cancelled.connect(worker.deleteLater)
        worker.cancelled.connect(self.thread.quit)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

    @Slot(str)
    def append_log(self, message: str) -> None:
        if "正在保存大图" not in message and "RIIN正在" not in message:
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

    @Slot()
    def stop_current_task(self) -> None:
        if self.worker is None:
            return
        self.worker.request_cancel()
        self.stop_button.setEnabled(False)
        text = self.worker.stop_pending_text
        self.loading_label.setText(text)
        self.log.appendPlainText(text)

    @Slot()
    def task_cancelled(self) -> None:
        text = (
            self.worker.stopped_text
            if self.worker is not None
            else "当前处理已停止。"
        )
        self.loading_label.setText(text)
        self.log.appendPlainText(text)

    @Slot(object)
    def action_finished(self, result: dict) -> None:
        if result.get('type') == 'completed_erp_generated':
            self.completed_page.show_generation_result(result)
            return
        if result.get('type') == 'read':
            if result['kind'] == 'completed_erp':
                self.completed_page.show_result(result)
            elif result['kind'] == 's2b_preview':
                self.s2b_preview_page.show_result(result)
            else:
                self.local_read_finished(result)
            return
        from ..shell.results import present_action_result
        present_action_result(self, result)

    @Slot(str)
    def failed(self, message: str) -> None:
        self.log.appendPlainText(f"停止：{message}")
        QMessageBox.critical(self, "操作已停止", message)

    def _set_actions_enabled(self, enabled: bool) -> None:
        widgets = (
            self.platform,
            self.main_tabs,
            self.refresh_button,
            self.select_button,
            self.download_button,
            getattr(self, "automated_print_button", None),
            getattr(self, "remote_dispatch_button", None),
            getattr(self, "order_side_checkbox", None),
            getattr(self, "open_download_folder", None),
            self.process_button,
            self.merge_batches,
            self.range_button,
            self.settings_button,
            getattr(self, "preview_rules_button", None),
            getattr(self, "default_multi_preview_button", None),
            getattr(self, "route_preview_button", None),
            getattr(self, "route_selector", None),
            getattr(self, "local_refresh_button", None),
            getattr(self, "local_select_button", None),
            getattr(self, "local_process_button", None),
            getattr(self, "local_merge_batches", None),
            getattr(self, "local_open_button", None),
            getattr(self, "manual_layout_button", None),
            getattr(self, "label_quick_panel", self.settings_button),
        )
        for widget in widgets:
            if widget is not None:
                widget.setEnabled(enabled)
        if hasattr(self, 'completed_page'):
            self.completed_page.set_actions_enabled(enabled)
        if hasattr(self, 's2b_preview_page'):
            self.s2b_preview_page.set_actions_enabled(enabled)
        plan = self.pending_batch_plan
        if hasattr(self, "generate_rules_button"):
            self.generate_rules_button.setEnabled(
                enabled
                and plan is not None
                and bool(plan.nonempty_items)
                and plan.total_items + plan.excluded_count
                == plan.received_count
            )
        route_plan = getattr(self, "pending_route_plan", None)
        if hasattr(self, "route_generate_button"):
            self.route_generate_button.setEnabled(
                enabled and route_plan is not None
                and route_plan.item_count > 0
            )
        default_plan = getattr(self, "pending_default_multi_plan", None)
        if hasattr(self, "default_multi_generate_button"):
            self.default_multi_generate_button.setEnabled(
                enabled and default_plan is not None
                and default_plan.item_count > 0
            )

    @Slot()
    def clear_worker(self) -> None:
        self.loading_panel.hide()
        self.stop_button.setEnabled(False)
        self._set_actions_enabled(True)
        defer_finished_thread_cleanup(self, "thread", "worker")
        if getattr(self, 'pending_local_read', None) is not None:
            QTimer.singleShot(0, self._start_pending_local_read)
