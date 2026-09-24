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
    target = tmp_path / "automation-enabled"

    assert not automation_enabled(target=target)
    assert set_automation_enabled(False, target=target) is False
    assert not automation_enabled(target=target)
    assert set_automation_enabled(True, target=target) is True
    assert automation_enabled(target=target)


def test_automation_is_fail_closed_without_opt_in_file(tmp_path):
    assert not automation_enabled(target=tmp_path / "missing-enabled-marker")


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


def test_monitor_has_no_periodic_heartbeat_and_ignores_eta_changes():
    monitor = monitor_module.PrintExpMonitor(
        send=lambda _status: None, automation_allowed=lambda: False,
    )
    base = {
        "state": "running", "phase": "PrintExp打印中", "source_online": True,
        "progress_percent": 42, "batch_id": "batch", "batch_name": "batch.prn",
        "batch_info": {"printer_state": "printing"}, "remaining_seconds": 120,
        "error_message": None,
    }
    changed_eta = {**base, "remaining_seconds": 118}

    assert not hasattr(monitor, "heartbeat_seconds")
    assert monitor_module._signature(base) == monitor_module._signature(changed_eta)


def test_monitor_retries_failed_event_report_without_waiting_for_a_heartbeat(monkeypatch):
    attempts = []
    monkeypatch.setattr(monitor_module, "running_installations", lambda: [])
    monkeypatch.setattr(monitor_module, "find_installation", lambda: None)
    monkeypatch.setattr(monitor_module, "process_running", lambda: False)

    def send(_status):
        attempts.append("send")
        if len(attempts) == 1:
            raise OSError("offline")

    monitor = monitor_module.PrintExpMonitor(send=send, automation_allowed=lambda: True)
    monitor.run_once()
    monitor.run_once()
    monitor.run_once()

    assert attempts == ["send", "send"]


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
