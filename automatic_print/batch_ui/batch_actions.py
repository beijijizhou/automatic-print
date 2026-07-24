from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QTableWidgetItem,
)

from ..automation.batch_browser import BatchRecord
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

    def status_finished(self, status) -> None:
        name = self.platform.currentText()
        color = "#c62828" if status.accepted_count else "#2e7d32"
        self.accepted_summary.setText(
            f"{name}：<span style='color:{color};font-size:16px;"
            f"font-weight:700;'>{status.accepted_count} 个</span>"
            "已接单订单尚未进入生产中。"
        )
        self.cleared_table.setRowCount(0)
        if status.cleared:
            self.cleared_summary.setText(
                f"{name}：生产中为 0，平台已清单。"
            )
            self.cleared_table.setRowCount(1)
            for column, value in enumerate(
                [name, "—", "—", "0", "—", "已清单"]
            ):
                self.cleared_table.setItem(
                    0, column, QTableWidgetItem(value)
                )
        else:
            self.cleared_summary.setText(
                f"{name}：生产中还有 {status.production_count} 个。"
            )

    def batches_finished(self, records: list[BatchRecord]) -> None:
        self.records = records
        self.table.setRowCount(len(records))
        ready = 0
        for row, record in enumerate(records):
            box = QCheckBox()
            box.setEnabled(record.production_images_ready)
            self.table.setCellWidget(row, 0, box)
            values = (
                record.batch_number,
                str(record.item_count),
                str(record.piece_count),
                record.batch_type,
                record.created_at,
                "可下载" if record.production_images_ready else "生成中",
            )
            for column, value in enumerate(values, start=1):
                self.table.setItem(
                    row, column, QTableWidgetItem(value)
                )
            ready += int(record.production_images_ready)
        self.summary.setText(
            f"{self.platform.currentText()}：显示 {len(records)} 个最新批次，"
            f"{ready} 个生产图可下载。"
        )
        if self.range_start.text().strip() and self.range_end.text().strip():
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
        self.preferences.setValue(
            "automation/output_location", self.output.text().strip()
        )
        self._start_worker(
            AutomationWorker(
                "download",
                self.platform.currentData(),
                output=Path(self.output.text().strip()),
                batch_numbers=selected,
                settings=self._current_layout_settings(),
                sample_limit=5 if self.test_mode.isChecked() else None,
            )
        )

    def process_batches(self) -> None:
        output = Path(self.output.text().strip())
        if not output.is_dir():
            QMessageBox.warning(
                self, "找不到文件夹", "请选择包含已下载生产图的文件夹。"
            )
            return
        self._start_worker(
            AutomationWorker(
                "process",
                self.platform.currentData(),
                output=output,
                settings=self._current_layout_settings(),
                sample_limit=5 if self.test_mode.isChecked() else None,
            )
        )

    def open_settings(self) -> None:
        window = self.window()
        if hasattr(window, "open_settings_dialog"):
            window.open_settings_dialog()
