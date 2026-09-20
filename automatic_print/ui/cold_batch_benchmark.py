"""Developer dialog for an isolated ten-batch cold-cache DTF run."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)
from .folder_dialog_paths import DEFAULT_DTF_SHARE


class ColdBatchBenchmarkDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.process = None
        self.output = None
        self._buffer = ""
        self.setWindowTitle("开发者 · DTF 随机10批冷启动测试")
        self.resize(850, 600)
        layout = QVBoxLayout(self)
        note = QLabel(
            "从 DTF 日期目录的 HL / HL 2 中随机抽 10 个真实批次，逐批完整生成 PNG。"
            "每批使用独立空缓存；不清空 Windows 文件缓存，不写回 DTF 盘，不生成 PRN 或打印。"
            "测试大图可能占用数 GB 本机空间。")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.root = QLineEdit(str(DEFAULT_DTF_SHARE))
        self.destination = QLineEdit(str(Path.home() / "Documents"))
        source = QHBoxLayout()
        source.addWidget(self.root)
        browse_source = QPushButton("浏览…")
        browse_source.clicked.connect(self._browse_source)
        source.addWidget(browse_source)
        target = QHBoxLayout()
        target.addWidget(self.destination)
        browse_target = QPushButton("浏览…")
        browse_target.clicked.connect(self._browse_target)
        target.addWidget(browse_target)
        form.addRow("DTF 来源", source)
        form.addRow("本机测试目录", target)
        layout.addLayout(form)
        self.status = QLabel("尚未开始")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        actions = QHBoxLayout()
        self.start_button = QPushButton("随机抽取并测试10批")
        self.start_button.clicked.connect(self.start)
        self.open_button = QPushButton("打开测试结果")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_output)
        actions.addWidget(self.start_button)
        actions.addWidget(self.open_button)
        actions.addStretch()
        layout.addLayout(actions)

    def is_running(self):
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def _browse_source(self):
        selected = QFileDialog.getExistingDirectory(self, "选择 DTF 根目录", self.root.text())
        if selected:
            self.root.setText(selected)

    def _browse_target(self):
        selected = QFileDialog.getExistingDirectory(self, "选择本机测试结果位置", self.destination.text())
        if selected:
            self.destination.setText(selected)

    def start(self):
        if self.is_running() or self.window.has_active_tasks():
            self.status.setText("已有任务运行中，请等待其完成。")
            return
        if getattr(sys, "frozen", False):
            self.status.setText("此开发者测试需要源码 Python 环境；安装包不能作为 Python 子进程启动。")
            return
        source = Path(self.root.text().strip())
        base = Path(self.destination.text().strip())
        if not base.is_dir():
            self.status.setText(f"本机测试目录不存在：{base}")
            return
        if str(base).upper().startswith("Z:\\") or str(base).casefold().startswith(
            "\\\\192.168.11.28\\dtf".casefold()
        ):
            self.status.setText("测试结果必须保存在本机，不能写入 DTF 盘。")
            return
        if source == base or source in base.parents or base in source.parents:
            self.status.setText("本机结果目录不能位于 DTF 来源目录内，也不能包含 DTF 来源目录。")
            return
        settings = self.window._layout_settings()
        self.output = base / f"cold10-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:4]}"
        answer = QMessageBox.question(
            self, "确认冷启动测试",
            f"将只读扫描 {source}，随机抽 10 个 HL 批次，逐批生成到：\n{self.output}\n\n"
            "完整 PNG 可能占用数 GB；不使用现有应用缓存、不触发打印。现在开始吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        process = QProcess(self)
        process.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        process.readyReadStandardOutput.connect(self._read_output)
        process.readyReadStandardError.connect(self._read_error)
        process.finished.connect(self._finished)
        self.process = process
        self._buffer = ""
        self.log.clear()
        self.start_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.status.setText("正在启动独立冷缓存测试进程…")
        process.start(sys.executable, [
            "-m", "automatic_print.diagnostics.random_dtf", "--root", str(source),
            "--output", str(self.output), "--count", "10",
            "--settings-json", json.dumps(asdict(settings), ensure_ascii=False),
        ])
        if not process.waitForStarted(3000):
            self.status.setText(f"测试进程未启动：{process.errorString()}")
            self.start_button.setEnabled(True)

    def _read_output(self):
        self._buffer += bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            try:
                data = json.loads(line)
            except ValueError:
                if line.strip():
                    self.log.appendPlainText(line)
                continue
            event = data.get("event")
            if event == "scan":
                message = f"正在扫描：{data['folder']}"
            elif event == "batch_started":
                message = f"第{data['index']}/{data['count']}批 · {Path(data['folder']).name} · {data['images']}张 · 开始"
            elif event == "progress":
                message = f"第{data['index']}/{data['count']}批 · {data['stage']} · {data['detail']}"
            elif event == "batch_finished":
                message = (f"第{data['index']}批 {data['status']} · "
                           f"本批{data['wall_seconds']:.2f}秒 · 累计{data['cumulative_seconds']:.2f}秒")
            elif event == "finished":
                message = (f"{data['status']} · 成功{data['completed']}批 · 失败{data['failed']}批"
                           f" · 总计{data['total_seconds']:.2f}秒 · 报告：{data['report']}")
            else:
                message = data.get("error", line)
            self.status.setText(message)
            self.log.appendPlainText(message)

    def _read_error(self):
        detail = bytes(self.process.readAllStandardError()).decode("utf-8", "replace").strip()
        if detail:
            self.log.appendPlainText(detail)

    def _finished(self, exit_code, _exit_status):
        self._read_output()
        self._read_error()
        self.start_button.setEnabled(True)
        self.open_button.setEnabled(bool(self.output and self.output.exists()))
        if exit_code and not self.status.text().startswith(("部分失败", "扫描失败")):
            self.status.setText(f"测试进程异常退出（{exit_code}）；已生成结果保持原状，请查看日志。")

    def open_output(self):
        if self.output and self.output.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output)))

    def closeEvent(self, event):
        if self.is_running():
            self.hide()  # The user can hide the window without stopping the test.
            event.ignore()
            return
        super().closeEvent(event)
