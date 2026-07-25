from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QMessageBox,
    QTableWidgetItem,
)

from ..automation.local_batches import discover_local_batches
from ..layout import discover_images
from .worker import AutomationWorker


def image_name_rows(folder: Path) -> list[tuple[str, str]]:
    return [
        (image.name, str(image.relative_to(folder)))
        for image in discover_images(folder)
    ]


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
        self.filename_table.setRowCount(0)
        self.filename_summary.setText("选择一个本地批次查看图片名称。")
        if records:
            self.local_table.setCurrentCell(0, 1)

    def local_batch_changed(
        self, row: int, _column: int, _old_row: int, _old_column: int
    ) -> None:
        if row < 0 or self.local_table.item(row, 5) is None:
            return
        folder = Path(self.local_table.item(row, 5).text())
        images = image_name_rows(folder)
        self.filename_table.setRowCount(len(images))
        for index, (name, relative_path) in enumerate(images, start=1):
            values = (str(index), name, relative_path)
            for column, value in enumerate(values):
                self.filename_table.setItem(
                    index - 1, column, QTableWidgetItem(value)
                )
        batch_number = self.local_table.item(row, 2).text()
        self.filename_summary.setText(
            f"批次 {batch_number}：已读取 {len(images)} 个图片名称。"
        )
        self.filter_image_names(self.filename_search.text())

    def filter_image_names(self, text: str) -> None:
        keyword = text.strip().casefold()
        visible = 0
        for row in range(self.filename_table.rowCount()):
            name = self.filename_table.item(row, 1).text()
            matched = not keyword or keyword in name.casefold()
            self.filename_table.setRowHidden(row, not matched)
            visible += int(matched)
        if keyword:
            self.filename_summary.setText(f"找到 {visible} 个匹配的图片名称。")

    def copy_image_names(self) -> None:
        names = [
            self.filename_table.item(row, 1).text()
            for row in range(self.filename_table.rowCount())
        ]
        if not names:
            QMessageBox.warning(
                self, "没有文件名", "请先选择一个包含图片的本地批次。"
            )
            return
        QApplication.clipboard().setText("\n".join(names))
        self.filename_summary.setText(
            f"已复制 {len(names)} 个图片文件名。"
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
