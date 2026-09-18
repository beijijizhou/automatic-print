"""Local file reads run in the shared worker; widgets consume scoped results."""
from pathlib import Path
from PySide6.QtWidgets import QCheckBox, QTableWidgetItem

from ...automation.batches.naming import (
    MULTI_PIECE_TYPES, load_batch_type, sort_multi_piece_images,
)
from ...layout_engine import discover_images
from ..task.reads import ReadWorker


def image_name_rows(folder):
    images = discover_images(folder)
    if load_batch_type(folder) in MULTI_PIECE_TYPES:
        images = sort_multi_piece_images(images)
    return [(image.name, image.relative_to(folder).as_posix()) for image in images]


class LocalScanMixin:
    def _scan_scope(self):
        return self.output.text().strip(), self.platform.currentData()

    def _queue_local_read(self, kind, value=None):
        self.pending_local_read = ReadWorker(
            self.platform.currentData(), kind, self._scan_scope(), value)
        if self.thread is None:
            self._start_pending_local_read()

    def _start_pending_local_read(self):
        worker = getattr(self, 'pending_local_read', None)
        if worker is not None:
            self.pending_local_read = None
            if worker.scope == self._scan_scope():
                self._start_worker(worker)

    def refresh_local_batches(self):
        self.local_table.blockSignals(True)
        self.local_table.setRowCount(0)
        self.local_table.blockSignals(False)
        self.filename_table.setRowCount(0)
        self.local_summary.setText('正在后台读取本地批次…')
        self.filename_summary.setText('等待读取批次。')
        self._queue_local_read('local_batches')

    def local_batch_changed(self, row, _column, _old_row, _old_column):
        self.filename_table.setRowCount(0)
        if row < 0 or self.local_table.item(row, 5) is None:
            self.filename_summary.setText('请选择本地批次。')
            return
        folder = self.local_table.item(row, 5).text()
        self.filename_summary.setText('正在后台读取图片名称…')
        self._queue_local_read('image_names', folder)

    def local_read_finished(self, result):
        if result['scope'] != self._scan_scope():
            return
        if result['kind'] == 'local_batches':
            self._show_local_batches(result['data'])
            return
        row = self.local_table.currentRow()
        if row < 0 or self.local_table.item(row, 5).text() != result['value']:
            return
        images = result['data']
        self.filename_table.setRowCount(len(images))
        for index, (name, relative) in enumerate(images):
            for column, value in enumerate((str(index + 1), name, relative)):
                self.filename_table.setItem(index, column, QTableWidgetItem(value))
        self.filename_summary.setText(f'已读取 {len(images)} 个图片名称。')
        self.filter_image_names(self.filename_search.text())

    def _show_local_batches(self, records):
        self.local_table.blockSignals(True)
        self.local_table.setRowCount(len(records))
        self.local_select_button.setText('全选本地批次')
        for row, record in enumerate(records):
            self.local_table.setCellWidget(row, 0, QCheckBox())
            values = (record.platform_name, record.batch_number,
                      str(record.image_count), record.modified_at, str(record.folder))
            for column, value in enumerate(values, start=1):
                self.local_table.setItem(row, column, QTableWidgetItem(value))
        self.local_table.blockSignals(False)
        self.local_summary.setText(f'{self.platform.currentText()}：本地有 {len(records)} 个批次。')
        self.filename_summary.setText('选择一个本地批次查看图片名称。')
        if records:
            self.local_table.setCurrentCell(0, 1)
