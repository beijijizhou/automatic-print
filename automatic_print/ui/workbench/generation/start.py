"""Validate UI input and start a single background layout task."""

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from ....layout_engine.output_name import batch_output_directory
from ...busy_spinner import show_busy
from ...output_location import output_base
from ...workers import GenerateWorker


def start_generation(window, *, preview_only=False) -> None:
    preview_only = preview_only or window.automation_home.preview_only.isChecked()
    if not window.layout_generation.prepare():
        return
    source = Path(window.folder.text().strip())
    if not source.is_dir():
        QMessageBox.warning(window, "请选择文件夹", "请选择有效的图片文件夹。")
        return
    base = output_base(window, source)
    if not preview_only and not base.is_dir():
        QMessageBox.warning(window, "请选择保存位置", "请选择有效的任务保存位置。")
        return
    try:
        settings = window._layout_settings()
    except ValueError as error:
        QMessageBox.warning(window, "打印参数不正确", str(error))
        return

    window.generation_preview.start()
    job_id = datetime.now().strftime("JOB_%Y%m%d_%H%M%S")
    output = batch_output_directory(base, source.resolve().name, job_id)
    window.preferences.setValue("source_location", str(source))
    window.preferences.setValue("output_location", str(base))
    window.active_staging_output = output
    window.job_path.setText(str(base / "切膜机文件"))
    window.status.setText("正在开始：后台扫描图片文件名，再读取尺寸与排版…")
    window.current_file.setText("当前文件：—")
    window.progress.setValue(0)
    window.progress.setFormat("正在开始…")
    show_busy(window)
    window.run_log.clear()
    window.run_log.appendPlainText(f"任务：{job_id}")
    window.run_log.appendPlainText("正在后台扫描图片文件名…")
    window.run_log.appendPlainText(f"输出位置：{base / '切膜机文件'}")
    window.generate_button.setEnabled(False)
    window.stop_generation_button.setEnabled(True)
    window.started_at = time.monotonic()
    window.stage_started_at = window.started_at
    window.current_stage = "正在开始"
    window.current_count = 0
    window.current_total = 0
    window.active_png_compression = settings.png_compression_level
    window.active_png_engine = settings.png_engine
    window.clock.start()
    worker = GenerateWorker(
        None, source, output, job_id, settings, preview_only=preview_only
    )
    window.layout_generation.start(worker, window.worker_bridge)
