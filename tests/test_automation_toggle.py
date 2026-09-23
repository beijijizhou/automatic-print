import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from automatic_print.runtime.monitoring.control import (
    automation_enabled, decode_message, encode_message, set_automation_enabled,
)
from automatic_print.ui.automation_toggle import AutomationToggle
from automatic_print.automation.api.printerexp import monitor as monitor_module


APP = QApplication.instance() or QApplication([])


def test_disable_and_enable_persist_local_automation_state(tmp_path):
    target = tmp_path / "automation-disabled"

    assert set_automation_enabled(False, target=target) is False
    assert not automation_enabled(target=target)
    assert set_automation_enabled(True, target=target) is True
    assert automation_enabled(target=target)


def test_lan_wake_message_is_signed_and_expires():
    message = encode_message(False, key="k" * 32, timestamp=100, nonce="n")

    assert decode_message(message, key="k" * 32, now=101) is False
    assert decode_message(message + b"x", key="k" * 32, now=101) is None
    assert decode_message(message, key="k" * 32, now=131) is None


def test_toggle_explains_zero_cloud_traffic_and_changes_direction():
    toggle = AutomationToggle(read=lambda: True, write=lambda enabled: enabled)

    assert toggle.button.text() == "一键关闭全部自动化"
    assert "Supabase" in toggle.status.text()
    toggle._finished(False, "已发送关闭信号。")
    assert toggle.button.text() == "一键开启全部自动化"
    assert "关闭" in toggle.status.text()


def test_monitor_suppresses_reports_when_automation_is_disabled(monkeypatch):
    allowed = {"value": False}
    sent = []
    monkeypatch.setattr(monitor_module, "running_installations", lambda: [])
    monkeypatch.setattr(monitor_module, "find_installation", lambda: None)
    monkeypatch.setattr(monitor_module, "process_running", lambda: False)
    monitor = monitor_module.PrintExpMonitor(
        send=sent.append, automation_allowed=lambda: allowed["value"],
    )

    monitor.run_once()
    assert sent == []
    allowed["value"] = True
    monitor.run_once()
    assert sent and sent[-1]["source_online"] is False


def test_disabled_monitor_makes_no_cloud_dispatch_calls():
    events = []

    class OneLoop:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, _seconds):
            self.stopped = True

    wake = SimpleNamespace(
        start=lambda: events.append("wake-start"),
        stop=lambda: events.append("wake-stop"),
    )
    dispatcher = SimpleNamespace(tick=lambda: events.append("cloud"))
    monitor = monitor_module.PrintExpMonitor(
        automation_allowed=lambda: False,
        command_dispatcher=dispatcher,
        control_dispatcher=dispatcher,
        wake_listener=wake,
    )
    monitor.stop_event = OneLoop()

    monitor.run()

    assert events == ["wake-start", "wake-stop"]
