from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)

from ...automation.browser.batches import BatchRecord
from .cache import load_batch_cache, save_batch_cache
from ..task.worker import AutomationWorker


class BatchActionsMixin:
    def load_batch_range(self) -> None:
        start = self.range_start.currentText().strip()
        end = self.range_end.currentText().strip()
        if not (
            len(start) == 12
            and start.isdigit()
            and len(end) == 12
            and end.isdigit()
        ):
            QMessageBox.warning(
                self, "批次号不正确", "请输入两个完整的 12 位批次号。"
            )
            return
        self._start_worker(
            AutomationWorker(
                "list_range",
                self.platform.currentData(),
                range_start=start,
                range_end=end,
            )
        )

    def choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "选择本地批次文件所在位置", self.output.text()
        )
        if folder:
            self.output.setText(folder)
            self.preferences.setValue("automation/output_location", folder)

    @Slot(object)
    def status_finished(self, status) -> None:
        name = self.platform.currentText()
        color = "#c62828" if status.accepted_count else "#2e7d32"
        self.accepted_summary.setText(
            f"{name}：<span style='color:{color};font-size:16px;"
            f"font-weight:700;'>{status.accepted_count} 个</span>"
            "已接单订单尚未进入生产中。"
        )

    @Slot(object)
    def batches_finished(self, records: list[BatchRecord]) -> None:
        self.records = records
        saved_at = ""
        action = self.worker.action if self.worker is not None else ""
        if action == "list":
            saved_at = save_batch_cache(
                self.preferences,
                self.platform.currentData(),
                records,
            )
        self._display_batch_records(
            records, saved_at, select_ready=action == "list_range"
        )

    def show_cached_batches(self) -> None:
        records, saved_at = load_batch_cache(
            self.preferences, self.platform.currentData()
        )
        if records:
            self.records = records
            self._display_batch_records(records, saved_at, cached=True)
            return
        self.records = []
        self.table.setRowCount(0)
        self.summary.setText(
            f"{self.platform.currentText()}：暂无本地批次缓存，"
            "需要时请点击“刷新批次”。"
        )

    def _display_batch_records(
        self,
        records: list[BatchRecord],
        saved_at: str = "",
        cached: bool = False,
        select_ready: bool = False,
    ) -> None:
        from ..shell.batch_table import display_batch_records
        display_batch_records(self, records, saved_at, cached, select_ready)

    def select_all_ready(self) -> None:
        boxes = [
            self.table.cellWidget(row, 0)
            for row in range(self.table.rowCount())
            if self.table.cellWidget(row, 0).isEnabled()
        ]
        if not boxes:
            return
        selected = not all(box.isChecked() for box in boxes)
        for box in boxes:
            box.setChecked(selected)
        self.select_button.setText(
            "取消全选" if selected else "全选可下载批次"
        )

    def download_selected(self) -> None:
        self._download_selected(auto_print=False)

    def download_and_print_selected(self) -> None:
        self._download_selected(auto_print=True)

    def _selected_batch_numbers(self) -> list[str]:
        return [
            self.table.item(row, 1).text()
            for row in range(self.table.rowCount())
            if self.table.cellWidget(row, 0).isChecked()
        ]

    def _download_selected(self, *, auto_print: bool) -> None:
        selected = self._selected_batch_numbers()
        if not selected:
            QMessageBox.warning(
                self, "请选择批次", "请至少选择一个可下载批次。"
            )
            return
        if (
            not self.download_only
            and self.merge_batches.isChecked()
            and len(selected) < 2
        ):
            QMessageBox.warning(
                self, "请选择多个批次", "合并排版请至少选择两个批次。"
            )
            return
        self.preferences.setValue(
            "automation/output_location", self.output.text().strip()
        )
        batch_types = {
            record.batch_number: record.batch_type
            for record in self.records
            if record.batch_number in selected
        }
        shared_mode = auto_print in ('shared_knife', 'shared_knife_order_side')
        options = {
            "output": Path(self.output.text().strip()),
            "batch_numbers": selected,
            "batch_types": batch_types,
            "auto_print": auto_print,
        }
        if auto_print or not self.download_only:
            options.update(
                settings=self._current_layout_settings(),
                sample_limit=(5 if self.test_mode.isChecked() and
                              auto_print != 'shared_knife_order_side' else None),
                merge_batches=self.merge_batches.isChecked() and not shared_mode,
                preview_only=(False if auto_print
                              else self.download_preview_only.isChecked()),
            )
        self._start_worker(AutomationWorker(
            "download", self.platform.currentData(), **options))

    def process_batches(self) -> None:
        output = Path(self.output.text().strip())
        if not output.is_dir():
            QMessageBox.warning(
                self, "找不到文件夹", "请选择包含已下载生产图的文件夹。"
            )
            return
        selected = self._selected_batch_numbers()
        if self.merge_batches.isChecked() and len(selected) < 2:
            QMessageBox.warning(
                self, "请选择多个批次", "合并排版请至少选择两个批次。"
            )
            return
        self._start_worker(
            AutomationWorker(
                "process",
                self.platform.currentData(),
                output=output,
                batch_numbers=selected,
                settings=self._current_layout_settings(),
                sample_limit=5 if self.test_mode.isChecked() else None,
                batch_types={
                    record.batch_number: record.batch_type
                    for record in self.records
                },
                merge_batches=self.merge_batches.isChecked(),
                preview_only=self.download_preview_only.isChecked(),
            )
        )

    def open_settings(self) -> None:
        window = self.window()
        if hasattr(window, "open_settings_dialog"):
            window.open_settings_dialog()
