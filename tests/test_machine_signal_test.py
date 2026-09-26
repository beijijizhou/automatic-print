from automatic_print.automation.api.machine_status import commands
from automatic_print.ui import machine_signal_test
from automatic_print.ui.machine_signal_test import (
    probe_machine, run_machine_signal_test, signal_result_text,
)


def machine(number, version="0.1.411"):
    return {
        "machine_id": f"id-{number}", "machine_name": f"M{number}",
        "app_version": version,
    }


def test_realtime_only_probe_bypasses_lan(monkeypatch):
    cloud = []
    monkeypatch.setattr(
        commands, "notify_machine",
        lambda *_args, **_options: (_ for _ in ()).throw(AssertionError("LAN used")),
    )
    monkeypatch.setattr(
        commands, "notify_machine_via_cloud",
        lambda target, **options: cloud.append((target, options)) or True,
    )
    monkeypatch.setattr(
        commands, "_call", lambda *_args, **_options: {"command": {"id": "probe-cloud"}},
    )

    result = commands.submit_probe("machine-8", realtime_only=True)

    assert result["id"] == "probe-cloud"
    assert cloud == [("machine-8", {"command_id": "probe-cloud"})]


def test_probe_accepts_matching_live_identity():
    result = probe_machine(
        machine(2), submit=lambda _target: {"id": "probe-2"},
        fetch=lambda _command: {"status": "succeeded", "result": {
            "machine_id": "id-2", "machine_name": "M2",
            "app_version": "0.1.411", "automation_enabled": True,
            "source_online": False,
        }},
    )

    assert result == {
        "name": "M2", "stored_version": "0.1.411", "state": "responded",
        "version": "0.1.411", "automation_enabled": True, "source_online": False,
    }


def test_button_probe_defaults_to_realtime_only(monkeypatch):
    submitted = {}
    monkeypatch.setattr(
        machine_signal_test, "submit_probe",
        lambda target, **options: submitted.update(target=target, **options)
        or {"id": "probe-2"},
    )

    result = probe_machine(
        machine(2), fetch=lambda _command: {"status": "succeeded", "result": {
            "machine_id": "id-2", "machine_name": "M2", "app_version": "0.1.419",
        }},
    )

    assert result["state"] == "responded"
    assert submitted == {
        "target": "id-2", "expires_minutes": 3, "realtime_only": True,
    }


def test_probe_timeout_uses_configured_deadline():
    ticks = iter((0, 0, 5))

    result = probe_machine(
        machine(2), submit=lambda _target: {"id": "probe-2"},
        fetch=lambda _command: {"status": "queued"},
        deadline_seconds=5, poll_seconds=0,
        clock=lambda: next(ticks), wait=lambda _seconds: None,
    )

    assert result["state"] == "timeout"
    assert result["detail"] == "5 秒内未回应"


def test_fleet_signal_test_continues_when_one_machine_does_not_respond():
    def fake_probe(item):
        if item["machine_name"] == "M3":
            return {
                "name": "M3", "stored_version": "0.1.411",
                "state": "timeout", "detail": "12 秒内未回应",
            }
        return {
            "name": item["machine_name"], "stored_version": item["app_version"],
            "state": "responded", "version": item["app_version"],
        }

    report = run_machine_signal_test([machine(3), machine(1, "0.1.410")], probe=fake_probe)
    text = signal_result_text(report)

    assert [item["name"] for item in report["results"]] == ["M1", "M3"]
    assert "Realtime 测试完成：已响应 1 / 2 · 未响应 1" in text
    assert "实时版本分布：0.1.410（1 台）" in text
    assert "M1 0.1.410" in text
    assert "M3 · 12 秒内未回应 · 上次 0.1.411" in text
