from automatic_print.ui.machine_signal_test import (
    probe_machine, run_machine_signal_test, signal_result_text,
)


def machine(number, version="0.1.411"):
    return {
        "machine_id": f"id-{number}", "machine_name": f"M{number}",
        "app_version": version,
    }


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
    report["current_version"] = "0.1.411"
    text = signal_result_text(report)

    assert [item["name"] for item in report["results"]] == ["M1", "M3"]
    assert "实时响应 1 / 2 · 当前版本 1 · 待更新 1" in text
    assert "M1 0.1.410" in text
    assert "待更新：M1 0.1.410" in text
    assert "M3（12 秒内未回应，上次版本 0.1.411）" in text
