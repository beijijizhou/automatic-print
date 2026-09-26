from types import SimpleNamespace

from automatic_print.automation.api.machine_commands.dispatcher import CommandDispatcher
from automatic_print.automation.api.machine_commands import runner
from automatic_print.automation.api.machine_commands.runner import CommandProgress, _layout_settings
from automatic_print.automation.api.printerexp.monitor import PrintExpMonitor


def test_dispatcher_claims_one_command_and_waits_for_process():
    claimed = []
    spawned = []
    process = SimpleNamespace(poll=lambda: None)

    def claim(timeout):
        claimed.append(timeout)
        return {"id": "command-1"}

    dispatcher = CommandDispatcher(
        poll_seconds=5,
        claim=claim,
        spawn=lambda command_id: spawned.append(command_id) or process,
    )
    dispatcher.tick(clock=lambda: 10)
    dispatcher.tick(clock=lambda: 20)

    assert claimed == [4]
    assert spawned == ["command-1"]
    assert dispatcher.process is process


def test_monitor_accepts_independent_control_dispatcher():
    download = SimpleNamespace(tick=lambda: None)
    control = SimpleNamespace(tick=lambda: None)

    monitor = PrintExpMonitor(
        send=lambda _status: None,
        command_dispatcher=download,
        control_dispatcher=control,
    )

    assert monitor.command_dispatcher is download
    assert monitor.control_dispatcher is control


def test_monitor_keeps_dispatch_pending_while_worker_is_busy():
    process = SimpleNamespace(poll=lambda: None)
    download = SimpleNamespace(tick=lambda: None, process=None, next_poll=0)
    control = SimpleNamespace(tick=lambda: None, process=process, next_poll=0)
    monitor = PrintExpMonitor(
        send=lambda _status: None,
        command_dispatcher=download,
        control_dispatcher=control,
    )

    monitor._tick_dispatchers(force=True)

    assert monitor.dispatch_event.is_set()


def test_command_progress_rate_limits_repeated_updates():
    sent = []
    progress = CommandProgress("command-1", send=lambda *a, **k: sent.append((a, k)), interval=999)
    progress("第一步", force=True)
    progress("第二步")

    assert len(sent) == 1
    assert sent[0][1]["phase"] == "第一步"


def test_runner_launches_only_the_fixed_application_and_reports_receipt(monkeypatch):
    updates = []
    monkeypatch.setattr(runner, "CommandProgress", lambda _command_id: lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "get_command", lambda _command_id: {
        "action": "launch_app", "payload": {},
    })
    monkeypatch.setattr(
        "automatic_print.runtime.application_launch.launch_application",
        lambda: {"launched": True, "already_running": False},
    )
    monkeypatch.setattr(
        runner, "update_command",
        lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    assert runner.run_command("launch-1") == 0
    assert updates[-1][0] == ("launch-1", "succeeded")
    assert updates[-1][1]["phase"] == "AutomaticPrint 主界面已启动"
    assert updates[-1][1]["result"]["launched"] is True


def test_remote_settings_keep_target_machine_number(tmp_path):
    from PySide6.QtCore import QSettings

    preferences = QSettings(str(tmp_path / "target-number.ini"), QSettings.IniFormat)
    preferences.setValue("layout/machine_number", "M8")
    settings = _layout_settings({"dpi": 200, "machine_number": "M1", "unknown": 3}, preferences)

    assert settings.dpi == 200
    assert settings.machine_number == "M8"


def test_remote_settings_use_target_machine_layout_snapshot(tmp_path):
    from PySide6.QtCore import QSettings
    from automatic_print.history.layout_settings import save_layout_settings
    from automatic_print.layout_engine import LayoutSettings

    preferences = QSettings(str(tmp_path / "target.ini"), QSettings.IniFormat)
    save_layout_settings(preferences, LayoutSettings(
        dpi=360, cutter_mode="single", machine_number="M8",
    ))
    settings = _layout_settings({
        "dpi": 200, "cutter_mode": "dual", "machine_number": "M1", "unknown": 3,
    }, preferences)

    assert settings.dpi == 360
    assert settings.cutter_mode == "single"
    assert settings.machine_number == "M8"


def test_s2b_remote_command_uses_s2b_batch_listing(monkeypatch):
    expected = [SimpleNamespace(batch_number="609180613013")]
    monkeypatch.setattr(
        runner, "load_batch_records",
        lambda platform, progress: expected if platform == "S2B" else [],
    )
    monkeypatch.setattr(
        runner, "load_batch_records_between",
        lambda *_args: (_ for _ in ()).throw(AssertionError("ERP range used")),
    )

    assert runner._load_selected_records(
        "S2B", ["609180613013"], lambda _message: None
    ) == expected


def test_remote_command_runs_download_layout_and_prn_in_order(tmp_path, monkeypatch):
    events = []
    batch = "609180613013"
    record = SimpleNamespace(
        batch_number=batch, production_images_ready=True, batch_type="S2B生产批次",
        batch_label="白色 S-XL",
    )
    preferences = SimpleNamespace(value=lambda key, default, value_type: (
        str(tmp_path) if key == "automation/output_location" else default
    ))
    monkeypatch.setattr(runner, "QSettings", lambda *_args: preferences)
    monkeypatch.setattr(
        runner, "_load_selected_records",
        lambda *_args: events.append("records") or [record],
    )
    monkeypatch.setattr(
        runner, "download_selected_batches",
        lambda *_args: events.append("download") or [tmp_path / "batch.zip"],
    )
    monkeypatch.setattr(
        runner, "save_downloaded_batch_types",
        lambda *_args: events.append("types"),
    )
    processed = {
        "batches": [(batch, {"filename": "final.png"})],
        "output_folder": str(tmp_path / "S2B" / "PROCESSED"),
    }
    layout_options = {}
    def process(*_args, **kwargs):
        layout_options.update(kwargs)
        events.append("layout")
        return processed
    monkeypatch.setattr(runner, "process_local_batches", process)
    monkeypatch.setattr(
        "automatic_print.automation.api.riin.jobs.generate_batch_prns",
        lambda *_args: events.append("prn") or ([{"batch": batch, "output": "job.prn"}], [], []),
    )

    result = runner.execute_download_layout(
        {
            "platform": "S2B",
            "batch_numbers": [batch],
            "layout_settings": {"dpi": 300},
            "generate_prn": True,
        },
        lambda *_args, **_kwargs: None,
    )

    assert events == ["records", "download", "types", "layout", "prn"]
    assert layout_options["batch_labels"] == {batch: "白色 S-XL"}
    assert result["prn_files"] == ["job.prn"]
    assert result["physical_print_started"] is False


def test_runner_routes_pause_command_without_starting_layout(monkeypatch):
    updates = []
    monkeypatch.setattr(runner, "get_command", lambda _command_id: {
        "action": "pause_print", "payload": {},
    })
    monkeypatch.setattr(
        runner, "execute_printer_action",
        lambda action, progress, payload: {"state": "paused", "action": action},
    )
    monkeypatch.setattr(
        runner, "update_command", lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    assert runner.run_command("command-1") == 0
    assert updates[-1][0][1] == "succeeded"
    assert updates[-1][1]["phase"] == "PrintExp 已暂停"


def test_runner_answers_probe_with_fresh_machine_facts(monkeypatch):
    updates = []
    monkeypatch.setattr(runner, "get_command", lambda _command_id: {
        "action": "probe", "payload": {},
    })
    monkeypatch.setattr(runner, "inspect_machine", lambda: {
        "machine_id": "machine-1", "machine_name": "M1",
        "app_version": "0.1.386",
        "source_online": True, "status": {"state": "idle"},
    })
    monkeypatch.setattr(
        runner, "update_command", lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    assert runner.run_command("probe-1") == 0
    assert updates[-1][0][1] == "succeeded"
    assert updates[-1][1]["phase"] == "目标机实时检测通过"
    assert updates[-1][1]["result"]["machine_name"] == "M1"


def test_runner_reads_printexp_history_only_when_requested(monkeypatch):
    updates = []
    monkeypatch.setattr(runner, "get_command", lambda _command_id: {
        "action": "probe", "payload": {"request": "printer_history", "limit": 20},
    })
    monkeypatch.setattr(
        "automatic_print.automation.api.printerexp.history.read_print_history",
        lambda limit, days: {"records": [{"task_name": "job.prn"}], "total_records": 1},
    )
    monkeypatch.setattr(
        runner, "update_command", lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    assert runner.run_command("history-1") == 0
    assert updates[-1][1]["phase"] == "PrintExp 打印历史读取完成"
    assert updates[-1][1]["result"]["records"][0]["task_name"] == "job.prn"


def test_runner_routes_start_with_expected_batch(monkeypatch):
    captured = {}
    monkeypatch.setattr(runner, "get_command", lambda _command_id: {
        "action": "start_print", "payload": {"expected_batch_name": "tangle.prn"},
    })
    monkeypatch.setattr(
        runner, "execute_printer_action",
        lambda action, progress, payload: captured.update(action=action, payload=payload) or {
            "state": "printing",
        },
    )
    monkeypatch.setattr(runner, "update_command", lambda *_args, **_kwargs: None)

    assert runner.run_command("command-start") == 0
    assert captured == {
        "action": "start_print", "payload": {"expected_batch_name": "tangle.prn"},
    }


def test_runner_marks_prn_error_as_failed_and_preserves_result(monkeypatch):
    updates = []
    result = {
        "prn_errors": [{"batch": "609240119004", "error": "PrintExp 装载失败"}],
        "prn_files": [], "physical_print_started": False,
    }
    monkeypatch.setattr(runner, "get_command", lambda _command_id: {
        "action": "download_layout", "payload": {},
    })
    monkeypatch.setattr(runner, "execute_download_layout", lambda *_args: result)
    monkeypatch.setattr(runner, "CommandProgress", lambda _command_id: lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        runner, "update_command", lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    assert runner.run_command("command-failed") == 1
    assert updates[-1][0][1] == "failed"
    assert updates[-1][1]["phase"] == "PRN生成或装载失败"
    assert updates[-1][1]["result"] == result
    assert "PrintExp 装载失败" in updates[-1][1]["error_message"]
