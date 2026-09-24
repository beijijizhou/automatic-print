from automatic_print.automation.api.machine_status.preflight import (
    MachinePreflightError,
    preflight_machine,
)


def test_preflight_waits_for_matching_live_printer_response():
    replies = iter([
        {"status": "queued"},
        {"status": "claimed"},
        {"status": "succeeded", "result": {
            "machine_id": "machine-1", "machine_name": "M1",
            "app_version": "0.1.386",
            "source_online": True,
            "status": {"state": "running", "batch_name": "current.prn"},
        }},
    ])
    now = [0.0]

    result = preflight_machine(
        "machine-1", "M1",
        submit=lambda target: {"id": f"probe-{target}"},
        fetch=lambda _command: next(replies),
        clock=lambda: now[0], wait=lambda seconds: now.__setitem__(0, now[0] + seconds),
    )

    assert result["machine_name"] == "M1"
    assert result["status"]["batch_name"] == "current.prn"


def test_preflight_rejects_ack_without_printexp():
    try:
        preflight_machine(
            "machine-1", "M1",
            submit=lambda _target: {"id": "probe-1"},
            fetch=lambda _command: {"status": "succeeded", "result": {
                "machine_id": "machine-1", "machine_name": "M1",
                "app_version": "0.1.386",
                "source_online": False,
            }},
        )
    except MachinePreflightError as error:
        assert "PrintExp 没有连接" in str(error)
    else:
        raise AssertionError("PrintExp 离线时不应通过发送前检测")


def test_preflight_does_not_require_an_automation_switch():
    result = preflight_machine(
        "machine-1", "M1",
        submit=lambda _target: {"id": "probe-1"},
        fetch=lambda _command: {"status": "succeeded", "result": {
            "machine_id": "machine-1", "machine_name": "M1",
            "app_version": "0.1.386",
            "source_online": True,
        }},
    )

    assert result["machine_name"] == "M1"


def test_preflight_timeout_does_not_send_production_task():
    now = [0.0]
    try:
        preflight_machine(
            "machine-8", "M8", deadline_seconds=2, poll_seconds=1,
            submit=lambda _target: {"id": "probe-8"},
            fetch=lambda _command: {"status": "queued"},
            clock=lambda: now[0], wait=lambda seconds: now.__setitem__(0, now[0] + seconds),
        )
    except MachinePreflightError as error:
        assert "没有回应" in str(error)
        assert "未发送生产任务" in str(error)
    else:
        raise AssertionError("超时探测不应被视为可用")
