from types import SimpleNamespace

from automatic_print.automation.api.machine_commands.dispatcher import CommandDispatcher
from automatic_print.automation.api.machine_commands import runner
from automatic_print.automation.api.machine_commands.runner import CommandProgress, _layout_settings


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


def test_command_progress_rate_limits_repeated_updates():
    sent = []
    progress = CommandProgress("command-1", send=lambda *a, **k: sent.append((a, k)), interval=999)
    progress("第一步", force=True)
    progress("第二步")

    assert len(sent) == 1
    assert sent[0][1]["phase"] == "第一步"


def test_remote_settings_keep_target_machine_number():
    preferences = SimpleNamespace(value=lambda key, default, value_type: "M8")
    settings = _layout_settings({"dpi": 200, "machine_number": "M1", "unknown": 3}, preferences)

    assert settings.dpi == 200
    assert settings.machine_number == "M8"


def test_runner_routes_pause_command_without_starting_layout(monkeypatch):
    updates = []
    monkeypatch.setattr(runner, "get_command", lambda _command_id: {
        "action": "pause_print", "payload": {},
    })
    monkeypatch.setattr(
        runner, "execute_printer_action",
        lambda action, progress: {"state": "paused", "action": action},
    )
    monkeypatch.setattr(
        runner, "update_command", lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    assert runner.run_command("command-1") == 0
    assert updates[-1][0][1] == "succeeded"
    assert updates[-1][1]["phase"] == "PrintExp 已暂停"
