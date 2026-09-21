"""UV 亿点万象批次选择和下载；网络工作始终在后台线程。"""

from pathlib import Path
from math import ceil

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHeaderView, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..layout_engine.uv import identify_uv_batch_material, uv_sheet_capacity


class YdwxWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, action, selected=(), output=None):
        super().__init__()
        self.action = action
        self.selected, self.output = tuple(selected), output

    @Slot()
    def run(self):
        try:
            from ..automation.api.ydwx import download_batches, list_batches
            result = (
                list_batches()
                if self.action == "list" else
                download_batches(self.selected, self.output, self.progress.emit)
            )
            self.finished.emit((self.action, result))
        except Exception as error:
            self.failed.emit(str(error))


class YdwxDownloadPage(QWidget):
    idle = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.host_window = window
        self.thread = self.worker = None
        self.records = []
        self.output = QLineEdit(
            window.preferences.value("uv/ydwx_output", "", str)
        )
        browse = QPushButton("选择保存位置…")
        browse.clicked.connect(self.choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output, 1)
        output_row.addWidget(browse)

        self.refresh = QPushButton("读取生产批次")
        self.refresh.clicked.connect(self.load_batches)
        self.download = QPushButton("下载并按 UV 材质分组")
        self.download.clicked.connect(self.download_selected)
        self.download.setEnabled(False)
        actions = QHBoxLayout()
        actions.addWidget(self.refresh)
        actions.addWidget(self.download)
        actions.addStretch()
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["选择", "日期", "批次名称", "批次号", "稿件已下载/总数", "产品件数",
             "识别材质", "每画布/预计组数"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.status = QLabel("通过共享登录服务读取批次；勾选具体批次才会下载。")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "当前以 UV 为主；亿点万象也有 DTF 订单。接口未提供可靠的部门字段，"
            "请按具体批次核对归属后勾选。下载与排版分开进行。"
            "平台的“下载剩余/重新下载”可能改变稿件下载计数。"
            "表格组数按接口稿件数预估，下载后以 ZIP 实际图片数分组；"
            "例如 1-7 表示第 1 组有 7 张，不是 7 个文件夹。原 ZIP 保留。"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addWidget(QLabel("下载保存位置"))
        layout.addLayout(output_row)
        layout.addLayout(actions)
        layout.addWidget(self.status)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.log)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择亿点万象下载保存位置", self.output.text()
        )
        if path:
            self.output.setText(path)
            self.host_window.preferences.setValue("uv/ydwx_output", path)

    def load_batches(self):
        self.records = []
        self.table.setRowCount(0)
        self.download.setEnabled(False)
        self._start("list")

    def download_selected(self):
        selected = [
            self.records[row] for row in range(self.table.rowCount())
            if self.table.cellWidget(row, 0).isChecked()
        ]
        if not selected:
            self.status.setText("请先勾选要下载的批次名称。")
            return
        output = Path(self.output.text().strip())
        if not output.is_dir():
            self.status.setText("保存位置不存在；请选择有效文件夹。")
            return
        self.host_window.preferences.setValue("uv/ydwx_output", str(output))
        self._start("download", selected, output)

    def _start(self, action, selected=(), output=None):
        if self.thread is not None:
            return
        self.thread = QThread(self)
        self.worker = YdwxWorker(action, selected, output)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.finished.connect(self._finished)
        self.worker.failed.connect(self._failed)
        for signal in (self.worker.finished, self.worker.failed):
            signal.connect(self.worker.deleteLater)
            signal.connect(self.thread.quit)
        self.thread.finished.connect(self._clear)
        self.refresh.setEnabled(False)
        self.download.setEnabled(False)
        self.status.setText("正在读取批次…" if action == "list" else "正在下载选中批次…")
        self.thread.start()

    @Slot(str)
    def _progress(self, message):
        self.status.setText(message)
        self.log.appendPlainText(message)

    @Slot(object)
    def _finished(self, result):
        action, value = result
        if action == "list":
            self.records = value
            self.table.setRowCount(len(value))
            for index, record in enumerate(value):
                box = QCheckBox()
                box.setEnabled(record.manuscript_count > 0)
                self.table.setCellWidget(index, 0, box)
                spec = identify_uv_batch_material(record.name)
                capacity = uv_sheet_capacity(spec) if spec else 0
                for column, text in enumerate((
                    record.date, record.name, record.number,
                    f"{record.downloaded_count}/{record.manuscript_count}",
                    str(record.product_count),
                    spec.label if spec else "未识别（只存 ZIP）",
                    (f"{capacity} 张 / 预计 {ceil(record.manuscript_count / capacity)} 组"
                     if capacity else "待核对"),
                ), 1):
                    self.table.setItem(index, column, QTableWidgetItem(text))
            self.status.setText(f"已读取 {len(value)} 个批次；请选择名称后下载。")
        else:
            saved, failures = value
            self.status.setText(
                f"完成：{len(saved)} 个批次原 ZIP 已保存，{len(failures)} 个分组待处理；"
                "“新增稿件”仅含本次未下载部分；下载不启动 UV 排版。"
            )
            for name, reason in failures:
                self.log.appendPlainText(f"{name}：{reason}")

    @Slot(str)
    def _failed(self, message):
        self.status.setText(f"本次操作未完成：{message}")
        self.log.appendPlainText(message)

    @Slot()
    def _clear(self):
        thread = self.thread
        self.thread = self.worker = None
        self.refresh.setEnabled(True)
        self.download.setEnabled(bool(self.records))
        thread.deleteLater()
        self.idle.emit()
