import pytest

from automatic_print.automation.api.printerexp.controls import (
    ALL_HEADS, MEDIUM_CLEAN, NativePrintExpControls, clean_then_resume, pause_print,
    start_print,
)
from automatic_print.automation.api.printerexp.state import PrintExpSnapshot


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def wait(self, seconds):
        self.value += seconds


class Controls:
    def __init__(self, caption="暂停", operation=None):
        self.caption = caption
        self.statuses = ["正在打印..."]
        self.pause_clicks = 0
        self.clean_clicks = 0
        self.clean_parameters = None
        self.print_clicks = 0
        self.operation = operation or ("paused" if caption == "继续" else "printing")

    def pause_caption(self):
        return self.caption

    def status_text(self):
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0]

    def click_pause(self):
        self.pause_clicks += 1
        self.caption = "继续" if self.caption == "暂停" else "暂停"
        if self.operation == "paused":
            self.operation = "printing"

    def click_clean(self):
        self.clean_clicks += 1
        self.statuses = ["正在清洗...", "正在清洗...", "打印暂停"]

    def configure_clean(self, head_group, strength):
        self.clean_parameters = (head_group, strength)

    def task_name(self):
        return "tangle.prn"

    def operation_state(self, task_loaded=False):
        return self.operation

    def click_print(self):
        self.print_clicks += 1
        self.operation = "printing"


def test_native_control_sends_button_command_to_parent():
    messages = []
    parent = type("Parent", (), {
        "send_message": lambda self, *args: messages.append(args),
    })()
    button = type("Button", (), {
        "handle": 4321,
        "parent": lambda self: parent,
    })()
    controls = object.__new__(NativePrintExpControls)
    controls._control = lambda control_id: button

    controls._command(11027)

    assert messages == [(0x0111, 11027, 4321)]


def test_pause_button_only_pauses_current_print():
    controls = Controls()
    clock = Clock()

    result = pause_print(controls, clock=clock, wait=clock.wait)

    assert result == {"state": "paused", "already_paused": False}
    assert controls.caption == "继续"
    assert controls.pause_clicks == 1


def test_clean_then_resume_keeps_existing_pause_and_waits_for_cleaning():
    controls = Controls(caption="继续")
    clock = Clock()

    result = clean_then_resume(controls, clock=clock, wait=clock.wait)

    assert result["cleaning_completed"] is True
    assert result["resumed"] is True
    assert result["auto_paused"] is False
    assert controls.clean_clicks == 1
    assert controls.clean_parameters == (ALL_HEADS, MEDIUM_CLEAN)
    assert controls.pause_clicks == 1
    assert controls.caption == "暂停"


def test_clean_then_resume_auto_pauses_before_cleaning():
    controls = Controls(caption="暂停")
    clock = Clock()

    result = clean_then_resume(controls, clock=clock, wait=clock.wait)

    assert result["auto_paused"] is True
    assert result["head_group"] == "all_8"
    assert result["clean_strength"] == "medium"
    assert controls.clean_clicks == 1
    assert controls.pause_clicks == 2
    assert controls.caption == "暂停"


def test_clean_then_resume_refuses_when_no_active_print_exists():
    controls = Controls(caption="暂停")
    controls.statuses = ["空闲"]
    controls.operation = "unknown"

    with pytest.raises(RuntimeError, match="不是正在打印"):
        clean_then_resume(controls)

    assert controls.clean_clicks == 0
    assert controls.pause_clicks == 0


def test_clean_then_resume_does_not_double_toggle_when_printexp_auto_resumes():
    controls = Controls(caption="继续")
    clock = Clock()
    original_status = controls.status_text

    def status_text():
        value = original_status()
        if value == "打印暂停" and controls.clean_clicks:
            controls.caption = "暂停"
        return value

    controls.status_text = status_text
    result = clean_then_resume(controls, clock=clock, wait=clock.wait)

    assert result["resumed_by_printexp"] is True
    assert controls.pause_clicks == 0


def test_native_control_persists_all_heads_medium_before_cleaning():
    values = {"GLOBAL_CLEAN_HEAD": 7, "GLOBAL_CLEAN_MODE": 1}

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class Registry:
        HKEY_CURRENT_USER = object()
        KEY_QUERY_VALUE = 1
        KEY_SET_VALUE = 2
        REG_DWORD = 4

        @staticmethod
        def OpenKey(*_args):
            return Key()

        @staticmethod
        def SetValueEx(_key, name, _reserved, _kind, value):
            values[name] = value

        @staticmethod
        def QueryValueEx(_key, name):
            return values[name], Registry.REG_DWORD

    controls = object.__new__(NativePrintExpControls)
    controls.configure_clean(registry=Registry)

    assert values == {"GLOBAL_CLEAN_HEAD": ALL_HEADS, "GLOBAL_CLEAN_MODE": MEDIUM_CLEAN}


def test_start_print_rechecks_zero_progress_and_exact_loaded_batch():
    controls = Controls(operation="ready")
    snapshot = PrintExpSnapshot("job", 0, "tangle.prn", "batch", 1)

    result = start_print("tangle.prn", controls, snapshot=snapshot)

    assert result["physical_print_started"] is True
    assert result["resumed"] is False
    assert result["batch_name"] == "tangle.prn"
    assert controls.print_clicks == 1


@pytest.mark.parametrize("progress,name", [(1, "tangle.prn"), (0, "other.prn")])
def test_start_print_refuses_stale_progress_or_batch(progress, name):
    controls = Controls(operation="ready")
    snapshot = PrintExpSnapshot("job", progress, "tangle.prn", "batch", 1)

    with pytest.raises(RuntimeError):
        start_print(name, controls, snapshot=snapshot)

    assert controls.print_clicks == 0


def test_start_print_resumes_the_exact_paused_batch():
    controls = Controls(caption="继续")
    controls.operation = "paused"
    snapshot = PrintExpSnapshot("job", 42, "tangle.prn", "batch", 1)

    result = start_print("tangle.prn", controls, snapshot=snapshot)

    assert result["resumed"] is True
    assert controls.pause_clicks == 1
    assert controls.print_clicks == 0
