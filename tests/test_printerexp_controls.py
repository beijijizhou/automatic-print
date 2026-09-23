import pytest

from automatic_print.automation.api.printerexp.controls import (
    NativePrintExpControls, clean_then_resume, pause_print,
)


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def wait(self, seconds):
        self.value += seconds


class Controls:
    def __init__(self, caption="暂停"):
        self.caption = caption
        self.statuses = ["正在打印..."]
        self.pause_clicks = 0
        self.clean_clicks = 0

    def pause_caption(self):
        return self.caption

    def status_text(self):
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0]

    def click_pause(self):
        self.pause_clicks += 1
        self.caption = "继续" if self.caption == "暂停" else "暂停"

    def click_clean(self):
        self.clean_clicks += 1
        self.statuses = ["正在清洗...", "正在清洗...", "打印暂停"]


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
    assert controls.pause_clicks == 1
    assert controls.caption == "暂停"


def test_clean_then_resume_auto_pauses_before_cleaning():
    controls = Controls(caption="暂停")
    clock = Clock()

    result = clean_then_resume(controls, clock=clock, wait=clock.wait)

    assert result["auto_paused"] is True
    assert controls.clean_clicks == 1
    assert controls.pause_clicks == 2
    assert controls.caption == "暂停"


def test_clean_then_resume_refuses_when_no_active_print_exists():
    controls = Controls(caption="暂停")
    controls.statuses = ["空闲"]

    with pytest.raises(RuntimeError, match="没有可确认的正在打印任务"):
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
