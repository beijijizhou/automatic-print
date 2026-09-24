"""Bridge ERP workflow progress into the fixed global activity center."""

import re
from time import monotonic

from PySide6.QtCore import QTimer


def begin_activity(owner, worker):
    owner.loading_bar.setRange(0, 0)
    owner._task_started_at = monotonic()
    owner._task_step_started_at = owner._task_started_at
    owner._task_step_number = 0
    owner._task_step_text = ""
    _ensure_timer(owner)
    hub = _hub(owner)
    if hub is not None:
        hub.begin(
            owner.activity_key,
            f"{worker.platform_name} · {worker.task_title}",
            f"正在启动 {worker.platform_name} · {worker.task_title}…",
            stop=owner.stop_current_task,
        )


def update_activity(owner, message):
    owner._task_step_number = getattr(owner, "_task_step_number", 0) + 1
    owner._task_step_text = message
    owner._task_step_started_at = monotonic()
    render_activity(owner)
    match = re.search(r"\[(\d+)/(\d+)\]", message)
    if match:
        current, total = map(int, match.groups())
        owner.loading_bar.setRange(0, total)
        owner.loading_bar.setValue(current)
        owner.loading_bar.setTextVisible(True)
        owner.loading_bar.setFormat(f"{current} / {total}")
    else:
        current = total = None
        owner.loading_bar.setRange(0, 0)
        owner.loading_bar.setTextVisible(False)
    hub = _hub(owner)
    if hub is not None:
        hub.update(
            owner.activity_key, message=message, current_object=message,
            current=current, total=total,
            progress_text=f"{current} / {total}" if total else "正在处理",
            new_step=True,
        )


def render_activity(owner):
    message = getattr(owner, "_task_step_text", "")
    if not message:
        return
    number = getattr(owner, "_task_step_number", 0)
    now = monotonic()
    step_seconds = int(now - getattr(owner, "_task_step_started_at", now))
    total_seconds = int(now - getattr(owner, "_task_started_at", now))
    elapsed = (
        f"（本步骤 {step_seconds} 秒 · 总计 {total_seconds} 秒）"
        if step_seconds > 0 else ""
    )
    owner.loading_label.setText(f"步骤 {number} · {message}{elapsed}")


def finish_activity(owner, message, state="completed"):
    timer = getattr(owner, "_task_status_timer", None)
    if timer is not None:
        timer.stop()
    hub = _hub(owner)
    if hub is not None:
        hub.finish(owner.activity_key, message, state=state)


def finish_running_activity(owner):
    hub = _hub(owner)
    if hub is None:
        return
    record = next(
        (item for item in hub.snapshot()["activities"]
         if item["key"] == owner.activity_key), None,
    )
    if record is not None and record["state"] == "running":
        finish_activity(owner, owner.loading_label.text() or "处理完成")


def _ensure_timer(owner):
    timer = getattr(owner, "_task_status_timer", None)
    if timer is None:
        timer = QTimer(owner)
        timer.setInterval(1_000)
        timer.timeout.connect(lambda: render_activity(owner))
        owner._task_status_timer = timer
    timer.start()


def _hub(owner):
    window = owner.window() if hasattr(owner, "window") else None
    return getattr(window, "activity_hub", None)
