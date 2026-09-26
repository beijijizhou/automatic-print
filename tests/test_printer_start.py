from pathlib import Path

from automatic_print.automation.api.machine_status import commands


ROOT = Path(__file__).parents[1]


def test_submit_start_print_carries_the_exact_expected_batch(monkeypatch):
    captured = {}
    monkeypatch.setattr(commands, "machine_id", lambda: "d9428888-122b-4c26-a127-3eafad1f5270")
    monkeypatch.setattr(commands, "machine_name", lambda: "M4")
    monkeypatch.setattr(commands, "notify_machine", lambda *args, **kwargs: True)
    monkeypatch.setattr(commands, "_call", lambda payload, **_options: captured.update(payload) or {
        "command": {"id": "control-start"}
    })

    commands.submit_printer_action(
        "b9428888-122b-4c26-a127-3eafad1f5271", "start_print",
        expected_batch_name="tangle.prn",
    )

    assert captured["command_action"] == "start_print"
    assert captured["payload"] == {"expected_batch_name": "tangle.prn"}


def test_backend_and_control_claim_allow_safety_gated_start():
    function = (ROOT / "supabase/functions/machine-status/index.ts").read_text(
        encoding="utf-8"
    )
    migration = (
        ROOT / "supabase/migrations/202609230004_start_print_control.sql"
    ).read_text(encoding="utf-8")
    action_migration = (
        ROOT / "supabase/migrations/202609230005_start_print_action.sql"
    ).read_text(encoding="utf-8")

    assert '"start_print"' in function
    assert 'printerState === "ready"' in function
    assert 'printerState === "paused"' in function
    assert 'task_name_verified !== true' in function
    assert "expected_batch_name" in function
    assert "start_print" in migration
    assert "machine_commands_action_check" in action_migration
    assert "'start_print'" in action_migration
