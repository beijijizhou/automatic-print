from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QMessageBox, QTableWidgetItem

from ..automation.local_batches import discover_local_batches
from .worker import AutomationWorker


class LocalActionsMixin:
    def refresh_local_batches(self) -> None:
        records = discover_local_batches(
            Path(self.output.text().strip()), self.platform.currentData()
        )
        self.local_table.setRowCount(len(records))
        self.local_select_button.setText("全选本地批次")
        for row, record in enumerate(records):
            self.local_table.setCellWidget(row, 0, QCheckBox())
            values = (
                record.platform_name,
                record.batch_number,
                str(record.image_count),
                record.modified_at,
                str(record.folder),
            )
            for column, value in enumerate(values, start=1):
                self.local_table.setItem(
                    row, column, QTableWidgetItem(value)
                )
        self.local_summary.setText(
            f"{self.platform.currentText()}：本地有 {len(records)} 个"
            "已下载批次，可直接排版，不访问生产平台。"
        )

    def select_all_local(self) -> None:
        boxes = [
            self.local_table.cellWidget(row, 0)
            for row in range(self.local_table.rowCount())
        ]
        if not boxes:
            return
        selected = not all(box.isChecked() for box in boxes)
        for box in boxes:
            box.setChecked(selected)
        self.local_select_button.setText(
            "取消全选" if selected else "全选本地批次"
        )

    def process_selected_local_batches(self) -> None:
        selected = [
            self.local_table.item(row, 2).text()
            for row in range(self.local_table.rowCount())
            if self.local_table.cellWidget(row, 0).isChecked()
        ]
        if not selected:
            QMessageBox.warning(
                self, "请选择批次", "请至少选择一个本地生产批次。"
            )
            return
        self._start_worker(
            AutomationWorker(
                "process",
                self.platform.currentData(),
                output=Path(self.output.text().strip()),
                batch_numbers=selected,
                settings=self._current_layout_settings(),
                sample_limit=5 if self.local_test_mode.isChecked() else None,
            )
        )

    def open_local_folder(self) -> None:
        folder = (
            Path(self.output.text().strip()) / self.platform.currentData()
        )
        if not folder.is_dir():
            QMessageBox.warning(
                self, "找不到文件夹", "当前平台还没有本地下载文件。"
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))
