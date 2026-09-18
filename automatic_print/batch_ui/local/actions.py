from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QMessageBox,
    QTableWidgetItem,
)

from ..task.worker import AutomationWorker
from .scanning import LocalScanMixin, image_name_rows


class LocalActionsMixin(LocalScanMixin):
    def open_manual_layout(self) -> None:
        window = self.window()
        if window.choose_folder():
            window.generate()

    def open_color_block_settings(self) -> None:
        window = self.window()
        window.color_block_settings.show()
        window.color_block_settings.raise_()
        window.color_block_settings.activateWindow()

    def open_label_settings(self) -> None:
        window = self.window()
        window.label_settings.exec()

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
        if self.local_merge_batches.isChecked() and len(selected) < 2:
            QMessageBox.warning(
                self, "请选择多个批次", "合并排版请至少选择两个批次。"
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
                merge_batches=self.local_merge_batches.isChecked(),
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
