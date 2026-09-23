"""Native PrintExp control discovery and state inspection."""

from pathlib import Path


PRINT_CONTROL_ID = 4
PAUSE_CONTROL_ID = 11027
CLEAN_CONTROL_ID = 11030
STATUS_CONTROL_ID = 31028
CLEAN_REGISTRY_PATH = r"Software\PrintExp_HS\PrintExp_X64\RIPRINT_EXE"
ALL_HEADS = 0
MEDIUM_CLEAN = 2


class NativePrintExpControls:
    def __init__(self):
        from pywinauto import Desktop

        self.window = Desktop(backend="win32").window(title="PrintExp")
        self.window.wait("exists ready", timeout=5)

    def pause_caption(self):
        return self._control(PAUSE_CONTROL_ID, require_enabled=False).window_text().strip()

    def status_text(self):
        return self._control(STATUS_CONTROL_ID, require_enabled=False).window_text().strip()

    def print_enabled(self):
        return self._enabled(PRINT_CONTROL_ID)

    def pause_enabled(self):
        return self._enabled(PAUSE_CONTROL_ID)

    def task_name(self):
        names = []
        for control in self.window.descendants():
            try:
                text = control.window_text().strip()
                visible = control.is_visible()
            except Exception:
                continue
            if visible and text.casefold().endswith(".prn"):
                name = Path(text.replace("\\", "/")).name
                if name.casefold() not in {item.casefold() for item in names}:
                    names.append(name)
        if len(names) != 1:
            raise RuntimeError("无法唯一确认 PrintExp 当前装载的 PRN 文件。")
        return names[0]

    def operation_state(self, task_loaded=False):
        caption = self.pause_caption()
        if "清洗" in self.status_text():
            return "cleaning"
        if self.pause_enabled():
            if caption == "继续":
                return "paused"
            if caption == "暂停":
                return "printing"
        if self.print_enabled() and not self.pause_enabled():
            return "ready" if task_loaded else "idle"
        return "unknown"

    def click_print(self):
        self._command(PRINT_CONTROL_ID)

    def click_pause(self):
        self._command(PAUSE_CONTROL_ID)

    def click_clean(self):
        self._command(CLEAN_CONTROL_ID)

    def configure_clean(self, head_group=ALL_HEADS, strength=MEDIUM_CLEAN, registry=None):
        if head_group != ALL_HEADS or strength != MEDIUM_CLEAN:
            raise ValueError("当前只允许 8 个喷头全部清洗、强度中。")
        if registry is None:
            import winreg as registry
        access = registry.KEY_QUERY_VALUE | registry.KEY_SET_VALUE
        with registry.OpenKey(
            registry.HKEY_CURRENT_USER, CLEAN_REGISTRY_PATH, 0, access,
        ) as key:
            registry.SetValueEx(key, "GLOBAL_CLEAN_HEAD", 0, registry.REG_DWORD, head_group)
            registry.SetValueEx(key, "GLOBAL_CLEAN_MODE", 0, registry.REG_DWORD, strength)
            saved_head = registry.QueryValueEx(key, "GLOBAL_CLEAN_HEAD")[0]
            saved_mode = registry.QueryValueEx(key, "GLOBAL_CLEAN_MODE")[0]
        if (saved_head, saved_mode) != (head_group, strength):
            raise RuntimeError("PrintExp 未保存清洗参数，未执行清洗。")

    def _enabled(self, control_id):
        try:
            return bool(self._control(control_id, require_enabled=False).is_enabled())
        except Exception:
            return False

    def _control(self, control_id, *, require_enabled=True):
        control = self.window.child_window(control_id=control_id).wrapper_object()
        if not control.is_visible() or (require_enabled and not control.is_enabled()):
            raise RuntimeError(f"PrintExp 控件不可操作：{control_id}")
        return control

    def _command(self, control_id):
        control = self._control(control_id)
        control.parent().send_message(0x0111, control_id, control.handle)
