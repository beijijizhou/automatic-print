"""Message-driven PrintExp pause and cleaning controls."""

from time import monotonic, sleep


PAUSE_CONTROL_ID = 11027
CLEAN_CONTROL_ID = 11030
STATUS_CONTROL_ID = 31028
class NativePrintExpControls:
    def __init__(self):
        from pywinauto import Desktop

        self.window = Desktop(backend="win32").window(title="PrintExp")
        self.window.wait("exists ready", timeout=5)

    def pause_caption(self):
        return self._control(PAUSE_CONTROL_ID).window_text().strip()

    def status_text(self):
        return self._control(STATUS_CONTROL_ID, require_enabled=False).window_text().strip()

    def click_pause(self):
        self._command(PAUSE_CONTROL_ID)

    def click_clean(self):
        self._command(CLEAN_CONTROL_ID)

    def _control(self, control_id, *, require_enabled=True):
        control = self.window.child_window(control_id=control_id).wrapper_object()
        if not control.is_visible() or (require_enabled and not control.is_enabled()):
            raise RuntimeError(f"PrintExp 控件不可操作：{control_id}")
        return control

    def _command(self, control_id):
        control = self._control(control_id)
        # pywinauto sends native WM_LBUTTONDOWN/UP messages directly to this
        # HWND. It neither moves the cursor nor depends on screen coordinates.
        control.click()


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
    _wait_until(
        lambda: controls.pause_caption() == "继续", timeout,
        "PrintExp 未在限定时间内进入暂停状态", clock, wait,
    )
    _report(progress, "PrintExp 已暂停")
    return {"state": "paused", "already_paused": False}


def clean_then_resume(
    controls=None, *, progress=None, start_timeout=10, clean_timeout=900,
    resume_timeout=10, clock=monotonic, wait=sleep,
):
    controls = controls or NativePrintExpControls()
    pause_result = pause_print(
        controls, progress=progress, timeout=start_timeout, clock=clock, wait=wait,
    )
    if _is_cleaning(controls.status_text()):
        raise RuntimeError("PrintExp 已经在清洗；保持暂停，请等待本次清洗结束。")
    _report(progress, "已确认暂停；正在启动 PrintExp 清洗")
    controls.click_clean()
    _wait_until(
        lambda: _is_cleaning(controls.status_text()), start_timeout,
        "PrintExp 未确认开始清洗；保持暂停，未执行继续打印", clock, wait,
    )
    _report(progress, "PrintExp 正在清洗；等待设备完成")
    _wait_until(
        lambda: not _is_cleaning(controls.status_text()), clean_timeout,
        "等待 PrintExp 清洗完成超时；保持暂停，未执行继续打印", clock, wait,
    )
    caption = controls.pause_caption()
    if caption == "暂停":
        _report(progress, "清洗完成，PrintExp 已自动继续打印")
        return {
            "state": "printing", "cleaning_completed": True,
            "resumed": True, "resumed_by_printexp": True,
            "auto_paused": not pause_result["already_paused"],
        }
    if caption != "继续":
        raise RuntimeError("清洗结束后无法确认暂停/打印状态；未发送启动指令。")
    _report(progress, "清洗完成；正在继续打印")
    controls.click_pause()
    _wait_until(
        lambda: controls.pause_caption() == "暂停", resume_timeout,
        "清洗已完成，但 PrintExp 未确认恢复打印", clock, wait,
    )
    _report(progress, "清洗完成，PrintExp 已继续打印")
    return {
        "state": "printing", "cleaning_completed": True,
        "resumed": True, "resumed_by_printexp": False,
        "auto_paused": not pause_result["already_paused"],
    }


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
