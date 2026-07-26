from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QTableWidgetItem,
)

from ..automation.batch_browser import BatchRecord
from ..automation.local_batches import discover_local_batches
from .batch_cache import load_batch_cache, save_batch_cache
from .worker import AutomationWorker


class BatchActionsMixin:
    def load_batch_range(self) -> None:
        start = self.range_start.text().strip()
        end = self.range_end.text().strip()
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
            self, "选择生产图保存位置", self.output.text()
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
        self.table.setRowCount(len(records))
        local_codes = {
            batch.batch_number
            for batch in discover_local_batches(
                Path(self.output.text().strip()),
                self.platform.currentData(),
            )
        }
        ready = 0
        for row, record in enumerate(records):
            is_local = record.batch_number in local_codes
            is_ready = record.production_images_ready or is_local
            box = QCheckBox()
            box.setEnabled(is_ready)
            self.table.setCellWidget(row, 0, box)
            values = (
                record.batch_number,
                str(record.item_count),
                str(record.piece_count),
                record.batch_type,
                record.created_at,
                (
                    "本地已有"
                    if is_local
                    else "可下载"
                    if is_ready
                    else "生成中"
                ),
            )
            for column, value in enumerate(values, start=1):
                self.table.setItem(
                    row, column, QTableWidgetItem(value)
                )
            ready += int(is_ready)
        self.summary.setText(
            f"{self.platform.currentText()}：显示 {len(records)} 个最新批次，"
            f"{ready} 个生产图可下载。"
            + (
                f" 当前为本地缓存，读取时间：{saved_at}。"
                if cached and saved_at
                else ""
            )
        )
        if select_ready:
            for row in range(self.table.rowCount()):
                box = self.table.cellWidget(row, 0)
                if box.isEnabled():
                    box.setChecked(True)
            self.select_button.setText("取消全选")

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
        selected = [
            self.table.item(row, 1).text()
            for row in range(self.table.rowCount())
            if self.table.cellWidget(row, 0).isChecked()
        ]
        if not selected:
            QMessageBox.warning(
                self, "请选择批次", "请至少选择一个可下载批次。"
            )
            return
        if self.merge_batches.isChecked() and len(selected) < 2:
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
        self._start_worker(
            AutomationWorker(
                "download",
                self.platform.currentData(),
                output=Path(self.output.text().strip()),
                batch_numbers=selected,
                settings=self._current_layout_settings(),
                sample_limit=5 if self.test_mode.isChecked() else None,
                batch_types=batch_types,
                merge_batches=self.merge_batches.isChecked(),
            )
        )

    def process_batches(self) -> None:
        output = Path(self.output.text().strip())
        if not output.is_dir():
            QMessageBox.warning(
                self, "找不到文件夹", "请选择包含已下载生产图的文件夹。"
            )
            return
        selected = [
            self.table.item(row, 1).text()
            for row in range(self.table.rowCount())
            if self.table.cellWidget(row, 0).isChecked()
        ]
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
            )
        )

    def open_settings(self) -> None:
        window = self.window()
        if hasattr(window, "open_settings_dialog"):
            window.open_settings_dialog()
