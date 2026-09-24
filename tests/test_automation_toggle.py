from types import SimpleNamespace
import base64
import json

from automatic_print.runtime.monitoring.control import (
    decode_dispatch_ack,
    decode_dispatch_message,
    decode_message,
    encode_dispatch_ack,
    encode_dispatch_message,
    encode_message,
)
from automatic_print.automation.api.printerexp import monitor as monitor_module
from automatic_print.runtime.monitoring import cloud_wake


def test_lan_wake_message_is_signed_and_expires():
    message = encode_message(False, key="k" * 32, timestamp=100, nonce="n")

    assert decode_message(message, key="k" * 32, now=101) is False
    assert decode_message(message + b"x", key="k" * 32, now=101) is None
    assert decode_message(message, key="k" * 32, now=131) is None


def test_targeted_dispatch_wake_is_signed_and_machine_specific():
    message = encode_dispatch_message(
        "machine-11", command_id="command-1", key="k" * 32,
        timestamp=100, nonce="n",
    )

    payload = decode_dispatch_message(message, key="k" * 32, now=101)

    assert payload["target_machine_id"] == "machine-11"
    assert payload["command_id"] == "command-1"
    assert decode_message(message, key="k" * 32, now=101) is None


def test_dispatch_ack_is_signed_and_tied_to_original_nonce():
    dispatch = decode_dispatch_message(encode_dispatch_message(
        "machine-11", command_id="command-1", key="k" * 32,
        timestamp=100, nonce="dispatch-nonce",
    ), key="k" * 32, now=100)

    acknowledgement = decode_dispatch_ack(encode_dispatch_ack(
        dispatch, key="k" * 32, timestamp=101, nonce="ack-nonce",
    ), key="k" * 32, now=101)

    assert acknowledgement["target_machine_id"] == "machine-11"
    assert acknowledgement["command_id"] == "command-1"
    assert acknowledgement["dispatch_nonce"] == "dispatch-nonce"


def test_cloud_topic_is_keyed_and_received_payload_stays_signed():
    received = []
    listener = cloud_wake.CloudWakeListener(
        target_machine_id="machine-11", dispatch=received.append, key="k" * 32,
    )
    message = encode_dispatch_message(
        "machine-11", command_id="command-1", key="k" * 32,
    )

    listener._receive({"payload": {
        "message": base64.b64encode(message).decode("ascii"),
    }})
    listener._receive({"payload": {"message": "not-signed"}})

    assert cloud_wake.machine_topic("machine-11", key="k" * 32).startswith(
        "automatic-print:dispatch:"
    )
    assert [item["command_id"] for item in received] == ["command-1"]


def test_cloud_publish_contains_only_a_signed_wake(monkeypatch):
    captured = {}

    class Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def open_request(request, timeout):
        captured.update(url=request.full_url, body=json.loads(request.data), timeout=timeout)
        return Response()

    monkeypatch.setattr(cloud_wake, "urlopen", open_request)
    cloud_wake.notify_machine_via_cloud(
        "machine-11", command_id="command-1", key="k" * 32, timeout=3,
    )

    signed = base64.b64decode(captured["body"]["message"])
    assert decode_dispatch_message(signed, key="k" * 32)["command_id"] == "command-1"
    assert "/events/machine-command" in captured["url"]
    assert captured["timeout"] == 3


def test_monitor_has_no_periodic_heartbeat_and_ignores_eta_changes():
    monitor = monitor_module.PrintExpMonitor(send=lambda _status: None)
    base = {
        "state": "running", "phase": "PrintExp打印中", "source_online": True,
        "progress_percent": 42, "batch_id": "batch", "batch_name": "batch.prn",
        "batch_info": {"printer_state": "printing"}, "remaining_seconds": 120,
        "error_message": None,
    }
    changed_eta = {**base, "remaining_seconds": 118}

    assert not hasattr(monitor, "heartbeat_seconds")
    assert monitor_module._signature(base) == monitor_module._signature(changed_eta)


def test_explicit_status_report_retries_after_failure(monkeypatch):
    attempts = []
    monkeypatch.setattr(monitor_module, "running_installations", lambda: [])
    monkeypatch.setattr(monitor_module, "find_installation", lambda: None)
    monkeypatch.setattr(monitor_module, "process_running", lambda: False)

    def send(_status):
        attempts.append("send")
        if len(attempts) == 1:
            raise OSError("offline")

    monitor = monitor_module.PrintExpMonitor(send=send)
    monitor.run_once()
    monitor.run_once()
    monitor.run_once()

    assert attempts == ["send", "send"]


def _one_loop():
    class OneLoop:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, _seconds):
            self.stopped = True

    return OneLoop()


def test_idle_monitor_checks_pending_commands_once_at_startup():
    events = []
    wake = SimpleNamespace(
        start=lambda: events.append("wake-start"),
        stop=lambda: events.append("wake-stop"),
    )
    dispatcher = SimpleNamespace(tick=lambda: events.append("cloud"))
    monitor = monitor_module.PrintExpMonitor(
        command_dispatcher=dispatcher,
        control_dispatcher=dispatcher,
        wake_listener=wake,
    )
    monitor.stop_event = _one_loop()

    monitor.run()

    assert events == ["wake-start", "cloud", "wake-stop"]


def test_idle_monitor_claims_once_after_targeted_wake():
    events = []
    wake = SimpleNamespace(
        start=lambda: events.append("wake-start"),
        stop=lambda: events.append("wake-stop"),
    )
    dispatcher = SimpleNamespace(next_poll=99, tick=lambda: events.append("claim"))
    monitor = monitor_module.PrintExpMonitor(
        command_dispatcher=dispatcher,
        control_dispatcher=dispatcher,
        wake_listener=wake,
    )
    monitor.stop_event = _one_loop()
    monitor.request_dispatch()

    monitor.run()

    assert events == ["wake-start", "claim", "claim", "claim", "wake-stop"]
