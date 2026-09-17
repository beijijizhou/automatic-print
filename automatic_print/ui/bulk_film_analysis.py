"""Visible, cancellable multi-folder comparison without printable output."""
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, QThread, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QListWidget, QAbstractItemView, QLabel, QPlainTextEdit, QSpinBox)
from ..runtime.cancellation import Cancellation
from ..history.bulk_analysis import analyze_folders, summary_text
from .action_icons import action_icon
from .folder_dialog_paths import image_dialog_start, remember_image_directory


class BulkAnalysisWorker(QObject):
    progress = Signal(int, str, str, int, int, str)
    finished = Signal(object)

    def __init__(self, folders, settings, parallelism=4):
        super().__init__()
        self.folders, self.settings = folders, settings
        self.cancellation = Cancellation()
        self.parallelism = parallelism

    @Slot()
    def run(self):
        try:
            result = analyze_folders(self.folders, self.settings, self.progress.emit,
                                     self.cancellation, parallelism=self.parallelism)
        except Exception as error:
            result = {'records': [], 'errors': [{'folder': '', 'error': str(error)}],
                      'stopped': False, 'seconds': 0}
        self.finished.emit(result)


class BulkFilmAnalysisDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('开发者 · 批量用膜数据分析（不生成最终文件）')
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(1000, 750)
        self.thread = self.worker = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('每个文件夹独立分析，不合并订单，不生成PNG；完成一批即保存历史。'))
        actions = QHBoxLayout()
        self.parent_add = QPushButton('添加上级目录中的批次')
        self.remove = QPushButton('移除选中')
        self.start = QPushButton('开始数据分析')
        self.stop = QPushButton('停止')
        self.start.setProperty('importance', 'primary')
        self.stop.setProperty('importance', 'danger')
        for button, icon in ((self.parent_add, 'folder'),
                             (self.remove, 'more'), (self.start, 'play'), (self.stop, 'stop')):
            button.setIcon(action_icon(icon))
            actions.addWidget(button)
        self.stop.setEnabled(False)
        layout.addLayout(actions)
        concurrency = QHBoxLayout()
        concurrency.addWidget(QLabel('同时分析批次数'))
        self.parallelism = QSpinBox()
        self.parallelism.setRange(1, 8)
        preferences = getattr(parent, 'preferences', None)
        self.parallelism.setValue(preferences.value('developer/bulk_parallelism', 4, int) if preferences else 4)
        concurrency.addWidget(self.parallelism)
        concurrency.addStretch()
        layout.addLayout(concurrency)
        self.folders = QListWidget()
        self.folders.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.folders)
        self.status = QLabel('选择上级目录，确认下面的批次后开始；45/60厘米，共4套。')
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)
        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        layout.addWidget(self.results)
        self.parent_add.clicked.connect(self.choose_parent)
        self.remove.clicked.connect(self.remove_selected)
        self.start.clicked.connect(self.begin)
        self.stop.clicked.connect(self.cancel)

    def add_folders(self, folders):
        existing = {self.folders.item(i).data(Qt.UserRole) for i in range(self.folders.count())}
        for folder in folders:
            path = Path(folder).resolve()
            if path.is_dir() and str(path) not in existing:
                self.folders.addItem(str(path))
                self.folders.item(self.folders.count()-1).setData(Qt.UserRole, str(path))
                existing.add(str(path))

    def choose_parent(self):
        folder = QFileDialog.getExistingDirectory(self, '选择包含多个批次的上级目录',
                                                 image_dialog_start(self.parent()))
        if folder:
            remember_image_directory(self.parent(), folder)
            self.add_folders(sorted(p for p in Path(folder).iterdir()
                                    if p.is_dir() and p.name != '切膜机文件'))

    def remove_selected(self):
        for item in self.folders.selectedItems():
            self.folders.takeItem(self.folders.row(item))

    def begin(self):
        if self.thread or not self.folders.count():
            return
        parent = self.parent()
        active = getattr(parent, 'thread', None)
        if isinstance(active, QThread) and active.isRunning():
            self.status.setText('请先停止当前排版，等待任务结束。')
            return
        try:
            settings = parent._layout_settings()
        except ValueError as error:
            self.status.setText(str(error))
            return
        folders = [Path(self.folders.item(i).data(Qt.UserRole)) for i in range(self.folders.count())]
        self.active_parallelism = min(self.parallelism.value(), len(folders))
        if hasattr(parent, 'preferences'):
            parent.preferences.setValue('developer/bulk_parallelism', self.parallelism.value())
            parent.preferences.sync()
        self.results.clear()
        self.status.setText(f'正在开始：同时分析{self.active_parallelism}批，后台扫描文件名…')
        self.set_busy(True)
        self.thread = QThread(self)
        self.worker = self.make_worker(folders, settings)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress, Qt.QueuedConnection)
        self.worker.finished.connect(self.complete, Qt.QueuedConnection)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.cleanup)
        self.thread.start()

    def make_worker(self, folders, settings):
        return BulkAnalysisWorker(folders, settings, self.parallelism.value())

    @Slot(int, str, str, int, int, str)
    def progress(self, index, folder, stage, current, total, filename):
        self.folders.item(index).setText(f'{Path(folder).name} · {stage} {current}/{total}\n{folder}')
        self.status.setText(f'并行{self.active_parallelism}批 · 批次 {index+1}/{self.folders.count()} · {Path(folder).name} · '
                            f'{stage} {current}/{total}\n{filename}')
        if stage in ('批次分析完成', '批次失败，继续下一批'):
            self.results.appendPlainText(self.status.text())

    @Slot(object)
    def complete(self, result):
        self.results.setPlainText(summary_text(result['records'])+'\n\n'+
            '\n'.join(f"{e['folder']}：{e['error']}" for e in result['errors']))
        self.status.setText(f"{'已停止' if result['stopped'] else '已完成'} · "
            f"成功保存 {len(result['records'])} 批 · 失败 {len(result['errors'])} 批 · "
            f"并行 {result.get('actual_parallelism', self.active_parallelism)} 批 · "
            f"耗时 {result['seconds']:.2f}秒；可在排版历史查看。")

    @Slot()
    def cleanup(self):
        self.thread.deleteLater()
        self.thread = self.worker = None
        self.set_busy(False)

    def set_busy(self, busy):
        for widget in (self.parent_add, self.remove, self.start, self.folders, self.parallelism):
            widget.setEnabled(not busy)
        self.stop.setEnabled(busy)

    def cancel(self):
        if self.worker:
            self.worker.cancellation.request()
            self.status.setText('正在安全停止；已完成批次的历史保留。')

    def reject(self):
        if self.thread:
            self.cancel()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.thread:
            self.cancel()
            event.ignore()
        else:
            super().closeEvent(event)
