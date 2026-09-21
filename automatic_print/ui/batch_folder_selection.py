"""Scan a chosen root off the GUI thread and let operators pick its batches."""
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPushButton,
    QHeaderView, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from ..layout_engine.intake.discovery.batch_discovery import scan_batches
from ..runtime.cancellation import Cancellation, TaskCancelled


class BatchFolderScanWorker(QObject):
    progress = Signal(str, int, int, str)
    finished = Signal(object)
    colors = Signal(object)
    done = Signal()

    def __init__(self, root):
        super().__init__()
        self.root = Path(root)
        self.cancellation = Cancellation()

    @Slot()
    def run(self):
        try:
            result = scan_batches(
                self.root, self.progress.emit, self.cancellation)
        except TaskCancelled:
            result = {'cancelled': True}
        except Exception as error:
            result = {'error': str(error)}
        self.finished.emit(result)
        try:
            if not result.get('cancelled') and not result.get('error'):
                from .batch_folder_colors import read_folder_colors
                colors = read_folder_colors(
                    result['batches'], self.cancellation, self.progress.emit)
                if colors:
                    self.colors.emit(colors)
        except TaskCancelled:
            pass
        except Exception as error:
            self.colors.emit({'_error': str(error)})
        finally:
            self.done.emit()


class BatchFolderSelectionDialog(QDialog):
    def __init__(self, parent, root):
        super().__init__(parent)
        self.root = Path(root)
        self.scan_result = None
        self.pending_reject = False
        self.pending_accept = False
        self.setWindowTitle('选择参与排版的文件夹')
        self.resize(980, 520)
        layout = QVBoxLayout(self)
        intro = QLabel(
            '勾选当前目录下需要排版的批次。“切膜机文件”输出目录会自动跳过。')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.status = QLabel('正在后台扫描批次文件夹…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.folders = QTreeWidget()
        self.folders.setHeaderLabels(('排版文件夹', '图片数', '颜色'))
        self.folders.setRootIsDecorated(False)
        self.folders.setAlternatingRowColors(True)
        self.folders.header().setStretchLastSection(False)
        self.folders.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.folders.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.folders)
        choices = QHBoxLayout()
        self.select_all = QPushButton('全选')
        self.clear_all = QPushButton('清空')
        choices.addWidget(self.select_all)
        choices.addWidget(self.clear_all)
        choices.addStretch()
        layout.addLayout(choices)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText('使用选中的文件夹')
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        layout.addWidget(self.buttons)
        self.select_all.clicked.connect(lambda: self._check_all(Qt.Checked))
        self.clear_all.clicked.connect(lambda: self._check_all(Qt.Unchecked))
        self.folders.itemChanged.connect(self._selection_changed)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.thread = QThread(self)
        self.worker = BatchFolderScanWorker(self.root)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.finished.connect(self._scanned)
        self.worker.colors.connect(self._colors)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_stopped)
        self.thread.start()

    @Slot(str, int, int, str)
    def _progress(self, stage, current, total, folder):
        if self.pending_accept or self.pending_reject:
            return
        if stage == 'S2B批次信息':
            self.status.setText(f'正在读取颜色 · {current}/{total} · {folder}')
        else:
            self.status.setText(f'正在扫描 · 已检查 {current} 个目录\n{folder}')

    @Slot(object)
    def _scanned(self, result):
        if self.pending_reject or result.get('cancelled'):
            self.pending_reject = True
            return
        if result.get('error'):
            self.status.setText(f"扫描失败：{result['error']}")
            return
        self.scan_result = result
        for batch in result['batches']:
            relative = batch['folder'].relative_to(self.root)
            label = self.root.name if not relative.parts else str(relative)
            from ..automation.api.s2b.metadata.batch_name import find_s2b_batch_folder
            is_s2b = any(find_s2b_batch_folder(path) for path in batch['images'][:1])
            item = QTreeWidgetItem((
                label, str(batch['image_count']), '读取中…' if is_s2b else '—'))
            item.setData(0, Qt.UserRole, batch)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked)
            item.setToolTip(0, str(batch['folder']))
            self.folders.addTopLevelItem(item)
        errors = len(result.get('errors', ()))
        suffix = f'；{errors} 个目录无法读取' if errors else ''
        self.status.setText(
            f"发现 {len(result['batches'])} 个图片批次，请取消不需要的勾选{suffix}。"
            if result['batches'] else f'没有发现可排版的图片批次{suffix}。')
        self._selection_changed()

    @Slot(object)
    def _colors(self, summaries):
        if self.pending_reject:
            return
        if '_error' in summaries:
            for index in range(self.folders.topLevelItemCount()):
                item = self.folders.topLevelItem(index)
                if item.text(2) == '读取中…':
                    item.setText(2, '未取得')
            self.status.setText(f"颜色读取失败：{summaries['_error']}；文件夹仍可选择。")
            return
        for index in range(self.folders.topLevelItemCount()):
            item = self.folders.topLevelItem(index)
            batch = item.data(0, Qt.UserRole)
            entry = summaries.get(str(batch['folder']))
            if entry:
                item.setText(2, entry[0])
                if entry[1]:
                    item.setToolTip(2, entry[1])
        self.status.setText('颜色已读取；请核对批次、图片数和颜色后选择文件夹。')

    def _check_all(self, state):
        for index in range(self.folders.topLevelItemCount()):
            self.folders.topLevelItem(index).setCheckState(0, state)

    @Slot()
    def _selection_changed(self, *_args):
        count = len(self.selected_batches())
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(count > 0)
        if self.scan_result:
            self.buttons.button(QDialogButtonBox.Ok).setText(
                f'使用选中的 {count} 个文件夹')

    def selected_batches(self):
        selected = []
        for index in range(self.folders.topLevelItemCount()):
            item = self.folders.topLevelItem(index)
            if item.checkState(0) == Qt.Checked:
                selected.append(item.data(0, Qt.UserRole))
        return selected

    def selected_scan(self):
        if self.scan_result is None:
            return None
        return dict(self.scan_result, batches=self.selected_batches(),
                    selected_batch_count=len(self.selected_batches()))

    @Slot()
    def _thread_stopped(self):
        if self.pending_reject:
            super().reject()
        elif self.pending_accept:
            super().accept()

    def accept(self):
        if self.thread.isRunning():
            self.pending_accept = True
            self.worker.cancellation.request()
            self.status.setText('正在结束后台颜色读取，随后使用已选文件夹…')
            return
        super().accept()

    def reject(self):
        if self.thread.isRunning():
            self.pending_reject = True
            self.worker.cancellation.request()
            self.status.setText('正在停止目录扫描…')
            return
        super().reject()


def choose_batch_folders(parent, root):
    dialog = BatchFolderSelectionDialog(parent, root)
    if dialog.exec() != QDialog.Accepted:
        return None
    return dialog.selected_scan()
