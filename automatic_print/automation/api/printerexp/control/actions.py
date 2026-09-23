"""Safety-gated PrintExp print, pause, and cleaning actions."""

from pathlib import Path
from threading import Thread
from time import monotonic, sleep

from ..discovery import running_installations
from ..state import read_snapshot
from .native import ALL_HEADS, MEDIUM_CLEAN, NativePrintExpControls


def start_print(
    expected_batch_name, controls=None, *, progress=None, timeout=10,
    clock=monotonic, wait=sleep, snapshot=None,
):
    expected = _name(expected_batch_name)
    if not expected:
        raise ValueError("开始打印前必须指定并确认批次文件名。")
    snapshot = snapshot if snapshot is not None else _current_snapshot()
    if snapshot is None or snapshot.progress != 0:
        raise RuntimeError("PrintExp 当前不是 0% 待打印状态，未开始打印。")
    loaded = {_name(snapshot.task_file), _name(snapshot.task_folder)} - {""}
    if expected not in loaded:
        raise RuntimeError("PrintExp 状态文件中的当前批次与待启动批次不一致。")
    controls = controls or NativePrintExpControls()
    if _name(controls.task_name()) != expected:
        raise RuntimeError("PrintExp 界面当前装载的 PRN 与待启动批次不一致。")
    if controls.operation_state(task_loaded=True) != "ready":
        raise RuntimeError("PrintExp 不是空闲待打印状态，未发送开始指令。")
    _report(progress, f"已确认待打印批次 {expected_batch_name}；正在开始物理打印")
    controls.click_print()
    _wait_until(
        lambda: controls.operation_state(task_loaded=True) == "printing", timeout,
        "PrintExp 未在限定时间内进入打印状态", clock, wait,
    )
    _report(progress, f"PrintExp 已开始打印 {expected_batch_name}")
    return {"state": "printing", "batch_name": expected_batch_name,
            "physical_print_started": True}


def pause_print(controls=None, *, progress=None, timeout=10, clock=monotonic, wait=sleep):
    controls = controls or NativePrintExpControls()
    caption = controls.pause_caption()
    if caption == "继续":
        _report(progress, "PrintExp 已经暂停，无需重复操作")
        return {"state": "paused", "already_paused": True}
    if caption != "暂停":
        raise RuntimeError(f"无法确认 PrintExp 暂停按钮，当前显示：{caption or '空白'}")
    if "打印" not in controls.status_text():
        raise RuntimeError("PrintExp 当前没有可确认的正在打印任务，未发送暂停指令。")
    _report(progress, "正在暂停 PrintExp 当前打印")
    controls.click_pause()
    _wait_until(lambda: controls.pause_caption() == "继续", timeout,
                "PrintExp 未在限定时间内进入暂停状态", clock, wait)
    _report(progress, "PrintExp 已暂停")
    return {"state": "paused", "already_paused": False}


def clean_then_resume(
    controls=None, *, progress=None, start_timeout=10, clean_timeout=900,
    resume_timeout=10, clock=monotonic, wait=sleep,
):
    controls = controls or NativePrintExpControls()
    configure = getattr(controls, "configure_clean", None)
    if configure:
        configure(ALL_HEADS, MEDIUM_CLEAN)
    _report(progress, "已设置 8 个喷头全部清洗，强度中")
    pause_result = pause_print(controls, progress=progress, timeout=start_timeout,
                               clock=clock, wait=wait)
    if _is_cleaning(controls.status_text()):
        raise RuntimeError("PrintExp 已经在清洗；保持暂停，请等待本次清洗结束。")
    _report(progress, "已确认暂停；正在启动 8 头中等强度清洗")
    command = _CleanCommand(controls.click_clean)
    command.start()
    started_at, observed_active = clock(), False
    while command.is_alive():
        observed_active = True
        if clock() - started_at >= clean_timeout:
            raise TimeoutError("等待 PrintExp 清洗完成超时；清洗命令仍在执行，未另行发送启动指令")
        wait(0.2)
    command.raise_error()
    if _is_cleaning(controls.status_text()):
        _wait_until(lambda: not _is_cleaning(controls.status_text()), clean_timeout,
                    "等待 PrintExp 清洗完成超时；保持暂停，未执行继续打印", clock, wait)
    elif not observed_active and controls.pause_caption() != "暂停":
        raise RuntimeError("PrintExp 未确认执行清洗；保持暂停，未执行继续打印")
    _report(progress, "PrintExp 清洗命令已完成")
    caption = controls.pause_caption()
    if caption == "暂停":
        return _clean_result(pause_result, True)
    if caption != "继续":
        raise RuntimeError("清洗结束后无法确认暂停/打印状态；未发送启动指令。")
    _report(progress, "清洗完成；正在继续打印")
    controls.click_pause()
    _wait_until(lambda: controls.pause_caption() == "暂停", resume_timeout,
                "清洗已完成，但 PrintExp 未确认恢复打印", clock, wait)
    _report(progress, "清洗完成，PrintExp 已继续打印")
    return _clean_result(pause_result, False)


def _current_snapshot():
    installations = running_installations()
    if not installations:
        return None
    latest = max(installations, key=_modified)
    return read_snapshot(latest)


def _modified(root):
    try:
        return (Path(root) / "Data" / "PrintInfo.ini").stat().st_mtime
    except OSError:
        return 0


def _name(value):
    return Path(str(value or "").replace("\\", "/")).name.casefold()


def _clean_result(pause_result, automatic):
    return {"state": "printing", "cleaning_completed": True, "resumed": True,
            "resumed_by_printexp": automatic,
            "auto_paused": not pause_result["already_paused"],
            "head_group": "all_8", "clean_strength": "medium"}


class _CleanCommand:
    def __init__(self, callback):
        self.error = None
        self.thread = Thread(target=self._run, args=(callback,), daemon=True)

    def start(self):
        self.thread.start()
        self.thread.join(0.01)

    def is_alive(self):
        return self.thread.is_alive()

    def raise_error(self):
        if self.error:
            raise self.error

    def _run(self, callback):
        try:
            callback()
        except Exception as error:
            self.error = error


def _wait_until(predicate, timeout, message, clock, wait):
    deadline = clock() + float(timeout)
    while clock() < deadline:
        if predicate():
            return
        wait(0.2)
    raise TimeoutError(message)


def _is_cleaning(value):
    return "清洗" in str(value)


def _report(callback, message):
    if callback:
        callback(message, force=True)
