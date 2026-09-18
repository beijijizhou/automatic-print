"""Developer control for local layout followed by RIIN PRN generation."""

import json
from pathlib import Path
import tempfile
from time import monotonic
import uuid

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout

from ..automation.api.riin.elevation import launch_elevated
from .automated_layout_files import (
    available_prn_path, existing_layout_pngs, generated_pngs,
)
from .progress_format import duration_text, file_size_text


class AutomatedLayoutControl(QGroupBox):
    """Continue the normal workbench task into RIIN and PrintExp."""

    def __init__(self, window, parent):
        super().__init__('自动生成打印文件（开发者）', parent)
        self.window = window
        self.busy = False
        self.direct_cutter_files = False
        self.source_path = self.output_path = None
        self._file_count = 0
        self._started_at = None
        self._report_path = self._manifest_path = None
        self.poller = QTimer(self)
        self.poller.setInterval(500)
        self.poller.timeout.connect(self._read_report)
        intro = QLabel(
            '原始批次先复用上方本地排版、进度、预览和结果；完成后自动交给RIIN生成PRN并加入PrintExp。'
            '已有“切膜机文件”可直接送RIIN，不解压、不二次排版。不会启动物理打印。')
        intro.setWordWrap(True)
        self.run_button = QPushButton('自动生成打印文件…')
        self.run_button.setMinimumHeight(40)
        self.run_button.clicked.connect(self.choose_and_start)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.run_button)
        self.setVisible(False)

    @property
    def summary(self):
        return self.window.automation_home.label_quick_panel.summary

    def _set_status(self, message, *, log=False):
        self.window.status.setText(message)
        self.summary.progress.setText(message)
        if log:
            self.window.run_log.appendPlainText(message)

    def choose_and_start(self):
        from .developer_mode import developer_task_active

        bulk_thread = getattr(
            getattr(self.window, 'bulk_controller', None), 'thread', None)
        conflicting_task = any((
            self.window.layout_generation.active,
            self.window.thread is not None,
            getattr(self.window, 'source_update_applying', False),
            developer_task_active(self.window),
            bulk_thread is not None,
        ))
        if self.busy or conflicting_task or not self.window.choose_folder():
            return
        source = Path(self.window.folder.text()).resolve()
        self.source_path = source
        self.output_path = available_prn_path(source)
        self.busy = True
        self.run_button.setEnabled(False)
        self.direct_cutter_files = source.name == '切膜机文件'
        if self.direct_cutter_files:
            try:
                files = existing_layout_pngs(source)
                self.summary.start(str(source), len(files))
                self.window.run_log.clear()
                self._launch_riin(files)
            except Exception as exc:
                self._fail(f'切膜机排版文件未导入RIIN：{exc}')
                return
            self._set_status(
                f'已识别 {len(files)} 个切膜机PNG；正在直接交给RIIN，不解压、不二次排版…',
                log=True)
            self.poller.start()
            return
        self._set_status('正在使用本地排版功能生成并验证最终PNG…', log=True)
        preview = self.window.automation_home.preview_only
        previous = preview.isChecked()
        preview.setChecked(False)
        try:
            from .bulk_workbench import start_bulk
            start_bulk(self.window, source)
        finally:
            preview.setChecked(previous)

    def local_layout_finished(self, result):
        if not self.busy:
            return
        if result.get('stopped') or result.get('errors'):
            errors = result.get('errors') or [{'error': '本地排版已停止'}]
            self._fail('本地排版未完成，未启动RIIN：' + errors[0]['error'])
            return
        try:
            files = generated_pngs(result.get('records', ()))
            self._launch_riin(files)
        except Exception as exc:
            self._fail(f'本地排版已完成，但RIIN任务未启动：{exc}')
            return
        self._set_status(
            f'本地排版及输出检查已完成；正在把 {len(files)} 个最终PNG导入RIIN…',
            log=True)
        self.poller.start()

    def _launch_riin(self, files):
        folder = Path(tempfile.gettempdir()) / 'AutomaticPrint' / 'riin-reports'
        folder.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        self._manifest_path = folder / f'{token}-files.json'
        self._report_path = folder / f'{token}-result.json'
        self._manifest_path.write_text(
            json.dumps([str(path) for path in files], ensure_ascii=False),
            encoding='utf-8')
        self._file_count = len(files)
        self._started_at = monotonic()
        launch_elevated([
            'automate-layout', '--report', str(self._report_path),
            '--manifest', str(self._manifest_path),
            '--output', str(self.output_path),
        ])

    def _read_report(self):
        if self._report_path and self._report_path.is_file():
            try:
                report = json.loads(self._report_path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                return
            if report.get('ok'):
                output = report.get('automation', {}).get('output', str(self.output_path))
                completed = ('切膜机文件已生成PRN' if self.direct_cutter_files
                             else '本地排版和PRN生成已完成')
                self._set_status(f'{completed}，已加入PrintExp：{output}', log=True)
                self._finish()
            else:
                error = report.get('error', '未知错误')
                self._fail(f'RIIN未完成PRN生成：{error}')
            return
        elapsed = duration_text(monotonic() - self._started_at)
        if self.output_path and self.output_path.is_file():
            size = file_size_text(self.output_path.stat().st_size)
            text = f'RIIN正在写入PRN · 已生成 {size} · 已用时 {elapsed}'
        else:
            text = f'RIIN正在导入并处理 {self._file_count} 个PNG · 已用时 {elapsed}'
        self._set_status(text)

    def _fail(self, message):
        self._set_status(message, log=True)
        self.summary.show_failure(message)
        self._finish()

    def _finish(self):
        self.poller.stop()
        self.busy = False
        self.run_button.setEnabled(True)
        for path in (self._report_path, self._manifest_path):
            if path:
                path.unlink(missing_ok=True)


def install_automated_layout_control(window, parent):
    control = AutomatedLayoutControl(window, parent)
    window.automated_layout_page = control  # Compatibility for task lifecycle.
    return control
