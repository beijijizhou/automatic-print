"""Render live generation stage, count, timing and file-size feedback."""

import time
from pathlib import Path

from ....controllers.generation_progress import (
    progress_count,
    progress_percent,
    remaining_seconds, report_machine_progress,
)
from ...busy_spinner import show_busy, show_progress
from ...progress_format import duration_text, file_size_text


def update_progress(window, stage, current, total, filename) -> None:
    filename = filename.split("\t", 1)[-1]
    percent = progress_percent(stage, current, total)
    if stage != window.current_stage:
        window.stage_started_at = time.monotonic()
        window.run_log.appendPlainText(f"开始：{stage}")
    window.current_stage = stage
    window.current_count = current
    window.current_total = total
    if stage == "保存图片":
        window.active_output_filename = filename
    if not total:
        show_busy(window)
    else:
        show_progress(window)
        window.progress.setRange(0, 100)
        window.progress.setValue(percent)
        window.progress.setFormat(f"{percent}% — {stage}")
    kind = "当前方案" if stage == "膜规格比较" else "当前文件"
    window.current_file.setText(f"{kind}：{filename}")
    refresh_timing(window)


def refresh_timing(window) -> None:
    now = time.monotonic()
    elapsed = now - window.started_at if window.started_at else 0
    stage_elapsed = now - window.stage_started_at if window.stage_started_at else 0
    remaining = remaining_seconds(
        window.current_stage,
        window.current_count,
        window.current_total,
        stage_elapsed,
    )
    estimate = (
        f"本阶段预计还需 {duration_text(remaining)}"
        if remaining is not None
        else "正在计算…"
    )
    count = progress_count(
        window.current_stage, window.current_count, window.current_total
    )
    window.status.setText(
        f"{window.current_stage}：{count}"
        f" · 本阶段 {duration_text(stage_elapsed)}"
        f" · 总计 {duration_text(elapsed)} · {estimate}"
        f"{saving_detail(window)}"
    )
    _publish_machine_progress(window, remaining)


def _publish_machine_progress(window, remaining) -> None:
    report_machine_progress(
        window,
        window.current_stage,
        progress_percent(
            window.current_stage, window.current_count, window.current_total
        ) if window.current_total else None,
        batch_info={
            "current": window.current_count,
            "total": window.current_total,
        },
        remaining=remaining,
    )


def saving_detail(window) -> str:
    if window.current_stage != "保存图片":
        return ""
    folder = getattr(window, "active_staging_output", window.job_path.text())
    filename = getattr(window, "active_output_filename", "")
    path = Path(folder) / filename
    try:
        size = path.stat().st_size
    except OSError:
        # Network output can be atomically renamed between existence and stat.
        size = 0
    return f" · 已写入 {file_size_text(size)}"
