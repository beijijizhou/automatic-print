"""Present preview, success, failure and cancellation results."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from ....automation.api.s2b.metadata.prepare import (
    metadata_summary_text, metadata_warning_text,
)
from ....layout_engine.reporting.metrics import saving_text
from ....layout_engine.output.output_file_info import production_summary_text
from ...busy_spinner import show_progress
from ...failure_dialog import show_failure_dialog
from ...progress_format import duration_text, file_size_text
from ...recent_output import remember_recent_output


def generation_finished(window, output, result) -> None:
    window.clock.stop()
    if window.generation_preview.mode == 'single':
        window.batch_status_board.update_batch(
            0, '批次预览完成' if result.get('preview_only') else '批次生成完成')
    if result.get("preview_only"):
        _show_preview_result(window)
        return
    timings = result["timings_seconds"]
    window.job_path.setText(output)
    remember_recent_output(window, output)
    show_progress(window)
    window.progress.setRange(0, 100)
    window.progress.setValue(100)
    window.progress.setFormat("100% — 已完成")
    window.status.setText(
        f"已完成 · 读取 {duration_text(timings['reading'])}"
        f" · 合成 {duration_text(timings['combining'])}"
        f" · 保存 {duration_text(timings['saving_png'])}"
        f" · 总计 {duration_text(timings['total'])}"
    )
    window.current_file.setText(f"当前文件：{result['filename']}")
    for name in result.get('files') or [result['filename']]:
        window.run_log.appendPlainText(f'已生成文件：{Path(output) / name}')
    window.run_log.appendPlainText(
        f"输出：{result['width_px']} × {result['height_px']} 像素"
        f" | 文件大小 {file_size_text(result['file_size_bytes'])}"
    )
    if result.get("trimmed_right_mm", 0) > 0:
        window.run_log.appendPlainText(
            f"已自动裁去右侧空白 {result['trimmed_right_mm']:.1f} 毫米"
        )
    saving = saving_text(result)
    summary = production_summary_text(result)
    metadata_records = result.get("analysis", {}).get("s2b_metadata", ())
    metadata_summary = metadata_summary_text(metadata_records)
    warning = metadata_warning_text(metadata_records)
    window.run_log.appendPlainText(summary)
    if metadata_summary:
        window.run_log.appendPlainText("S2B批次信息：\n" + metadata_summary)
    if warning:
        window.run_log.appendPlainText("S2B订单颜色提示：\n" + warning)
    window.run_log.appendPlainText(saving)
    window.status.setText(f"{window.status.text()} · {saving}")
    window.activity_hub.finish(
        "dtf-layout", window.status.text(), current_object=result["filename"],
    )
    _set_idle(window)
    if _confirm_result(window, output, summary, warning):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(output).resolve())))


def _show_preview_result(window) -> None:
    show_progress(window)
    window.progress.setRange(0, 100)
    window.progress.setValue(100)
    window.progress.setFormat("预览完成")
    window.status.setText("整批预览完成，未生成最终文件；尚未进行输出像素验收。")
    window.activity_hub.finish("dtf-layout", window.status.text())
    window.run_log.appendPlainText("仅预览完成：未生成打印文件。")
    window.job_path.clear()
    _set_idle(window)


def _confirm_result(window, output, summary, warning) -> bool:
    if not warning:
        QMessageBox.information(
            window, "生成完成", f"{summary}\n\n打印图片已保存到：\n{output}"
        )
        return True
    answer = QMessageBox.question(
        window,
        "订单颜色信息需要确认",
        f"{warning}\n\n文件已经生成，程序仍可继续使用。"
        "\n是否确认使用本次排版结果？",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    accepted = answer == QMessageBox.Yes
    decision = (
        "用户确认使用本次结果。"
        if accepted
        else "用户选择暂不使用；文件已保留供检查。"
    )
    window.run_log.appendPlainText(decision)
    window.status.setText(f"{window.status.text()} · {decision}")
    return accepted


def generation_failed(window, message) -> None:
    window.clock.stop()
    show_progress(window)
    window.progress.setRange(0, 100)
    window.progress.setFormat("生成失败")
    window.status.setText("生成失败；请查看报错诊断区。")
    window.activity_hub.finish("dtf-layout", window.status.text(), state="failed")
    window.run_log.appendPlainText(
        "生成失败；完整订单、参数及限制见独立报错诊断区。"
    )
    _set_idle(window)
    show_failure_dialog(window, message)


def generation_cancelled(window) -> None:
    window.clock.stop()
    show_progress(window)
    window.progress.setRange(0, 100)
    window.progress.setFormat("已停止")
    window.status.setText("当前排版已安全停止，已经完成的文件会保留。")
    window.activity_hub.finish("dtf-layout", window.status.text(), state="stopped")
    window.run_log.appendPlainText("当前排版已安全停止。")
    _set_idle(window)


def _set_idle(window) -> None:
    window.generate_button.setEnabled(True)
    window.stop_generation_button.setEnabled(False)
