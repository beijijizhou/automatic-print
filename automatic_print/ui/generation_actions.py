from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from ..layout import LayoutSettings, discover_images, discovered_extensions
from ..layout_engine.metrics import saving_text
from .workers import GenerateWorker
from .progress_format import duration_text, file_size_text
from .thread_lifecycle import (
    defer_finished_thread_cleanup,
    discard_stopped_thread,
)


class GenerationActionsMixin:
    def _layout_settings(self) -> LayoutSettings:
        label = self.label_settings
        return LayoutSettings(
            media_width_mm=self.width.value(),
            spacing_mm=self.spacing.value(),
            margin_mm=self.margin.value(),
            dpi=self.dpi.value(),
            png_compression_level=self.png_compression.currentData(),
            png_engine=self.png_engine.currentData(),
            worker_threads=self.worker_threads.value(),
            allow_rotation=self.allow_rotation.isChecked(),
            rotation_direction=self.rotation_direction.currentData(),
            number_images=self.number_images.isChecked(),
            number_gap_mm=label.gap.value(),
            number_font_size_mm=label.font_size.value(),
            label_text_template=label.text_template.text(),
            label_position=label.position.currentData(),
            label_offset_x_mm=label.offset_x.value(),
            label_offset_y_mm=label.offset_y.value(),
            label_date_format=label.date_format.text().strip() or "%Y-%m-%d",
        )

    def generate(self) -> None:
        if self.thread is not None and not discard_stopped_thread(
            self, "thread", "worker"
        ):
            return
        source = Path(self.folder.text().strip())
        if not source.is_dir():
            QMessageBox.warning(
                self, "请选择文件夹", "请选择有效的图片文件夹。"
            )
            return
        images = discover_images(source)
        if not images:
            types = discovered_extensions(source)
            found = "、".join(types[:15]) if types else "没有文件"
            QMessageBox.warning(
                self,
                "未找到图片",
                "所选文件夹中没有支持的图片。\n\n"
                f"实际发现的文件类型：{found}",
            )
            return
        base = Path(self.output_location.text().strip())
        if not base.is_dir():
            QMessageBox.warning(
                self, "请选择保存位置", "请选择有效的任务保存位置。"
            )
            return
        settings = self._layout_settings()
        job_id = datetime.now().strftime("JOB_%Y%m%d_%H%M%S")
        output = base / job_id
        self.preferences.setValue("source_location", str(source))
        self.preferences.setValue("output_location", str(base))
        self.job_path.setText(str(output))
        self.status.setText(f"已找到 {len(images)} 张图片，正在开始…")
        self.current_file.setText("当前文件：—")
        self.progress.setValue(0)
        self.progress.setFormat("正在开始…")
        self.run_log.clear()
        self.run_log.appendPlainText(f"任务：{job_id}")
        self.run_log.appendPlainText(f"图片数量：{len(images)}")
        self.run_log.appendPlainText(f"输出位置：{output}")
        self.generate_button.setEnabled(False)
        self.stop_generation_button.setEnabled(True)
        self.started_at = time.monotonic()
        self.stage_started_at = self.started_at
        self.current_stage = "正在开始"
        self.current_count = 0
        self.current_total = len(images)
        self.active_png_compression = settings.png_compression_level
        self.active_png_engine = settings.png_engine
        self.clock.start()
        self.thread = QThread(self)
        self.worker = GenerateWorker(
            images, source, output, job_id, settings
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        queued = Qt.ConnectionType.QueuedConnection
        bridge = self.worker_bridge
        self.worker.progress.connect(bridge.layout_progress, queued)
        self.worker.finished.connect(bridge.layout_finished, queued)
        self.worker.failed.connect(bridge.layout_failed, queued)
        self.worker.cancelled.connect(bridge.layout_cancelled, queued)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.worker.cancelled.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.failed.connect(self.worker.deleteLater)
        self.worker.cancelled.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

    @Slot(str, int, object, str)
    def update_progress(
        self, stage: str, current: int, total: int, filename: str
    ) -> None:
        if stage == "读取图片尺寸":
            percent = round(current / total * 45)
        elif stage == "合成图片":
            percent = 45 + round(current / total * 45)
        else:
            percent = 95
        if stage != self.current_stage:
            self.stage_started_at = time.monotonic()
            self.run_log.appendPlainText(f"开始：{stage}")
        self.current_stage = stage
        self.current_count = current
        self.current_total = total
        if stage == "保存图片":
            self.progress.setRange(0, 0)
            self.progress.setFormat("正在保存图片…")
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
            self.progress.setFormat(f"{percent}% — {stage}")
        self.current_file.setText(f"当前文件：{filename}")
        self.refresh_timing()

    @Slot()
    def refresh_timing(self) -> None:
        now = time.monotonic()
        elapsed = now - self.started_at if self.started_at else 0
        stage_elapsed = (
            now - self.stage_started_at if self.stage_started_at else 0
        )
        if self.current_count and self.current_stage in {
            "读取图片尺寸", "合成图片"
        }:
            left = self.current_total - self.current_count
            remaining = stage_elapsed / self.current_count * left
            estimate = f"本阶段预计还需 {duration_text(remaining)}"
        else:
            estimate = "正在计算…"
        saving_detail = self._saving_detail()
        count = (
            "正在持续写入磁盘"
            if self.current_stage == "保存图片"
            else f"{self.current_count}/{self.current_total}"
        )
        self.status.setText(
            f"{self.current_stage}：{count}"
            f" · 本阶段 {duration_text(stage_elapsed)}"
            f" · 总计 {duration_text(elapsed)} · {estimate}"
            f"{saving_detail}"
        )

    def _saving_detail(self) -> str:
        if self.current_stage != "保存图片":
            return ""
        path = Path(self.job_path.text()) / "print.png"
        size = path.stat().st_size if path.is_file() else 0
        return f" · 已写入 {file_size_text(size)}"

    @Slot()
    def stop_generation(self) -> None:
        if self.worker is None:
            return
        self.worker.request_cancel()
        self.stop_generation_button.setEnabled(False)
        self.status.setText(
            "正在安全停止；如果正在保存大图，将在当前文件写完后结束…"
        )
        self.run_log.appendPlainText("已请求停止当前排版。")

    @Slot(str, object)
    def generation_finished(self, output: str, result: dict) -> None:
        self.clock.stop()
        timings = result["timings_seconds"]
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("100% — 已完成")
        self.status.setText(
            f"已完成 · 读取 {duration_text(timings['reading'])}"
            f" · 合成 {duration_text(timings['combining'])}"
            f" · 保存 {duration_text(timings['saving_png'])}"
            f" · 总计 {duration_text(timings['total'])}"
        )
        self.current_file.setText("当前文件：print.png")
        self.run_log.appendPlainText(
            f"输出：{result['width_px']} × {result['height_px']} 像素"
            f" | 文件大小 {file_size_text(result['file_size_bytes'])}"
        )
        saving = saving_text(result)
        self.run_log.appendPlainText(saving)
        self.status.setText(f"{self.status.text()} · {saving}")
        self.generate_button.setEnabled(True)
        self.stop_generation_button.setEnabled(False)
        QMessageBox.information(
            self,
            "生成完成",
            f"{saving}\n\n打印图片已保存到：\n{output}",
        )
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(Path(output).resolve()))
        )

    @Slot(str)
    def generation_failed(self, message: str) -> None:
        self.clock.stop()
        self.progress.setRange(0, 100)
        self.progress.setFormat("生成失败")
        self.status.setText("生成失败。")
        self.run_log.appendPlainText(f"失败：{message}")
        self.generate_button.setEnabled(True)
        self.stop_generation_button.setEnabled(False)
        QMessageBox.critical(self, "生成失败", message)

    @Slot()
    def generation_cancelled(self) -> None:
        self.clock.stop()
        self.progress.setRange(0, 100)
        self.progress.setFormat("已停止")
        self.status.setText("当前排版已安全停止，已经完成的文件会保留。")
        self.run_log.appendPlainText("当前排版已安全停止。")
        self.generate_button.setEnabled(True)
        self.stop_generation_button.setEnabled(False)

    @Slot()
    def clear_worker(self) -> None:
        defer_finished_thread_cleanup(self, "thread", "worker")
