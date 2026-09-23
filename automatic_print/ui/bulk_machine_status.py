"""Machine-status adaptation for the rolling batch workbench."""

from datetime import datetime
from pathlib import Path
from time import monotonic

from ..controllers.generation_progress import (
    begin_machine_task, progress_percent, remaining_seconds,
    report_machine_progress,
)


def begin_status(owner, parent, batch_count):
    owner.machine_stage_started = {}
    begin_machine_task(
        owner.window,
        datetime.now().strftime("BULK_%Y%m%d_%H%M%S"),
        parent.name,
        batch_info={"batch_count": batch_count},
    )
    report_machine_progress(owner.window, "扫描文件夹", 0)


def update_status(owner, index, folder, stage, current, total):
    previous = owner.stages.get(index)
    if previous is None or previous[0] != stage:
        owner.machine_stage_started[index] = monotonic()
    elapsed = monotonic() - owner.machine_stage_started.get(index, monotonic())
    remaining = remaining_seconds(stage, current, total, elapsed)
    percent = progress_percent(stage, current, total) if total else None
    report_machine_progress(
        owner.window, stage, percent, remaining=remaining,
        batch_name=Path(folder).name,
        batch_info={"current": current, "total": total},
    )


def finish_status(owner, result, summary):
    state = "stopped" if result["stopped"] else (
        "failed" if result["errors"] and not result["records"] else "completed"
    )
    report_machine_progress(
        owner.window, summary, 100 if state == "completed" else None,
        state=state, remaining=0 if state == "completed" else None,
        batch_info={
            "completed_batches": len(result["records"]),
            "failed_batches": len(result["errors"]),
        },
        estimate_scope="batch" if state == "completed" else None,
    )
